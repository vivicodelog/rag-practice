"""
SSE（Server-Sent Events）流式推送。

把 Workflow 每步执行状态实时推给前端。
"""

import json
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from rag_forge.agent.workflow import Workflow, WorkflowNode
from rag_forge.agent.tools import search_docs, review_result
import backend.state as state

router = APIRouter()


@router.get("/chat/workflow/stream")
def stream_workflow(question: str = Query(..., description="用户问题")):
    """
    SSE 流式接口。

    EventSource 连接这个接口后，后端一步步推送事件：
      node_start → node_action → node_end → review_result → done
    """

    # 怎么让 FastAPI 返回流式响应？
    # 普通的 return 是等整个结果算完才返回，
    # StreamingResponse 可以一点一点吐出去。
    # 它接受一个 generator（生成器），每次 yield 就推一次。
    #
    # 提示：fastapi.responses.StreamingResponse

    def event_stream():
        # Step 1: 检查 vectordb 是否初始化
        # SSE 不能用 raise HTTPException（EventSource 会断开连接）
        # 所以错误也走流：yield 一个 error 事件，然后 return
        if state.vectordb is None:
            yield _sse("error", {"message": "索引未初始化"})
            return
        # Step 2: 组装三个 WorkflowNode
        #   researcher：role="researcher", tools=[search_docs], prompt 从 state 拿, output_type="text"
        #   writer：    role="writer",    tools=[],            prompt 从 state 拿
        #   reviewer：  role="reviewer",  tools=[review_result], prompt 从 state 拿, output_type="tool"
        # 三个 prompt 分别在 state.researcher_prompt / state.writer_prompt / state.reviewer_prompt
        researcher_node = WorkflowNode(
            role="researcher",
            tools=[search_docs],
            prompt=state.researcher_prompt,
            output_key="research",
            output_type="text"
        )
        writer_node = WorkflowNode(
            role="writer",
            tools=[],
            prompt=state.writer_prompt,
            output_key="answer",
            output_type="text"
        )
        reviewer_node = WorkflowNode(
            role="reviewer",
            tools=[review_result],
            prompt=state.reviewer_prompt,
            output_key="review",       # 不用 "answer"，不覆盖 Writer 的答案
            output_type="tool"
        )
        # Step 3: 创建 Workflow 实例，传 nodes 和 state.llm
        workflow = Workflow(
            nodes=[
                researcher_node,
                writer_node,
                reviewer_node,
            ],
            llm=state.llm,
        )
        # Step 4: 遍历 workflow.stream(question)
        #   stream() 每次 yield 一个 {"event": "...", "data": {...}}
        #   拿到的每个 event，用 _sse() 格式化后 yield 出去
        #   try/except 包一下，出错 yield error 事件，把错误包装成 SSE 事件正常返回（status 200），前端能读到错误消息
        try:
            for event in workflow.stream(question):
                yield _sse(event["event"], event["data"])
        except Exception as e:
            yield _sse("error", {"message": str(e)})
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    """
    拼 SSE 协议的文本格式。

    SSE 格式要求：
      event: 事件名\n
      data:  JSON 文本\n
      \n
    
    提示：返回的字符串里
      - event: 和 data: 后面各有一个空格
      - data 的值要用 json.dumps 转成字符串
      - 末尾两行 \n（空行是 SSE 的事件分隔符）
    """
    return f"event: {event}\ndata: {json.dumps(data,ensure_ascii=False)}\n\n"
