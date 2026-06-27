"""
SSE（Server-Sent Events）流式推送。

把 Workflow / Agent 的执行状态实时推给前端。
"""

import json
import os
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage

from backend.database import save_message
from rag_forge.agent.workflow import Workflow, WorkflowNode

from rag_forge.agent.tools import search_docs, review_result, get_weather,query_database
from rag_forge.config import settings
from rag_forge.retrieval.hybrid import hybrid_search
from rag_forge.history import trim_history
import backend.state as state

router = APIRouter()


@router.get("/chat/workflow/stream")
def stream_workflow(question: str = Query(..., description="用户问题"),history: str = Query("[]"),session_id: str = None):
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
        history_list = json.loads(history)  
        trimmed = trim_history(history_list, state.llm, settings.MAX_HISTORY_ROUNDS)        
        
        workflow = Workflow(
            nodes=[
                researcher_node,
                writer_node,
                reviewer_node,
            ],
            llm=state.llm,
            history=trimmed
        )
        # Step 4: 遍历 workflow.stream(question)
        #   stream() 每次 yield 一个 {"event": "...", "data": {...}}
        #   拿到的每个 event，用 _sse() 格式化后 yield 出去
        #   try/except 包一下，出错 yield error 事件，把错误包装成 SSE 事件正常返回（status 200），前端能读到错误消息
        try:
            for event in workflow.stream(question):
                if event["event"] == "node_end" and session_id and event["data"]["role"] == "writer":
                    save_message(session_id, "user", question) 
                    save_message(session_id, "assistant", event["data"]["output"])
                yield _sse(event["event"], event["data"])
            
        except Exception as e:
            yield _sse("error", {"message": str(e)})
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/chat/agent/stream")
def stream_agent(question: str = Query(..., description="用户问题"),history: str = Query("[]"),session_id: str = None):
    """                                                         history 参数收到的是 [{"role":"user","content":"hi"}] —— 一个JSON 格式的字符串
    SSE 流式问答。

    跟 /chat 一样是 Agent 模式（LLM 自主选工具），
    但用流式把 token 一个字一个字推给前端。
    """

    def event_stream():
        # Step 1: 检查 vectordb
        if state.vectordb is None:
            yield _sse("error", {"message": "索引未初始化"})
            return

        system_prompt = open(
            os.path.join(settings.PROMPTS_DIR, "system.md"),
            encoding="utf-8"
        ).read().strip()

        llm_with_tools = state.llm.bind_tools([get_weather, search_docs, query_database])
        history_list = json.loads(history)  
        trimmed = trim_history(history_list, state.llm, settings.MAX_HISTORY_ROUNDS)
        messages: list = [SystemMessage(content=system_prompt)]
        for msg in trimmed:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                messages.append(SystemMessage(content=msg["content"]))
        messages.append(HumanMessage(content=question))
        # 攒来源：search_docs 被调用时，顺手做 hybrid_search 拿详细来源
        sources = []
        final_answer = ""

        try:
            # Step 2: 工具调用循环（最多 3 轮，防死循环）
            for _ in range(3):
                # 用 llm_with_tools.stream() 代替 .invoke()
                # stream() 的每个 chunk 可能包含文字或工具调用信息
                # AIMessageChunk 可以用 + 累加，得到完整的响应
                collected = None  # 用来累加 chunk
                for chunk in llm_with_tools.stream(messages):
                    # chunk.content 是文本片段 → 立刻推给前端
                    if chunk.content:
                        yield _sse("token", {"text": chunk.content})
                    # 累加 chunk（AIMessageChunk 支持 + 运算）
                    collected = chunk if collected is None else collected + chunk
                
                	#           content	    tool_calls
                    # chunk 1	"好的，"	[]
                    # chunk 2	"我来查"	[{"name": "search_docs", "args": ...}"]`
                    # chunk 3	""	[{"args": ""天气""}]
                #collected → content="好的，我来查"，tool_calls[0] = 完整的 {"name": "search_docs", "args": {"query": "天气"}}

                #如果不加，拿 chunk 3 的 tool_calls，name 是空的——调用直接崩。
                if not collected:
                    break

                # Step 3: 检查 LLM 有没有调工具
                if collected.tool_calls:
                    # 把 LLM 的响应（含 tool_calls）放回消息列表
                    # 这是 API 的要求：ToolMessage 前面必须有对应的 tool_calls 消息
                    messages.append(collected)

                    # 告诉前端"开始调工具了"
                    yield _sse("tool_start", {"name": collected.tool_calls[0]["name"]})

                    # 执行每一个工具调用（逻辑跟 /chat 一样）
                    for tool_call in collected.tool_calls:
                        tool_name = tool_call["name"].lower()
                        tool_args = tool_call["args"]

                        if tool_name == "search_docs":
                            result = search_docs.invoke(tool_args)
                            if result not in ("未找到相关文档", "知识库尚未初始化，请先上传文档"):
                                raw = hybrid_search(
                                    query=tool_args["query"],
                                    vectordb=state.vectordb,
                                    all_chunks=state.all_chunks,
                                    top_k=6,
                                    reranker=state.reranker,
                                )
                                sources = [
                                    {"filename": os.path.basename(s) if s else "未知", "score": score, "content": c[:200]}
                                    for c, score, s in raw
                                ]
                        elif tool_name == "get_weather":
                            result = get_weather.invoke(tool_args)
                        else:
                            result = f"未知工具：{tool_name}"

                        # 把工具执行结果放回消息列表（所有工具都要放）
                        messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
                        yield _sse("tool_end", {"name": tool_name})
                    continue  # 继续下一轮（LLM 会基于工具结果生成回答）

                # 没调工具 → 这就是最终答案
                final_answer = collected.content
                if session_id:
                    save_message(session_id, "user", question)
                    save_message(session_id, "assistant", final_answer)
                break

            yield _sse("done", {"answer": final_answer, "sources": sources})

        except Exception as e:
            logger.exception("stream_agent error")
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
