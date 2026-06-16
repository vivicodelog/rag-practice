"""
SSE（Server-Sent Events）流式推送。

Workflow 执行时，把每一步的状态推给前端，
前端可以实时看到 Researcher → Writer → Reviewer 的进度。
"""

import json
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from backend.workflow import Workflow, WorkflowNode
from rag_forge.agent.tools import search_docs, review_result
import backend.state as state

router = APIRouter()


@router.get("/chat/workflow/stream")
def stream_workflow(question: str = Query(..., description="用户问题")):
    """SSE 流式接口：Workflow 执行过程逐事件推送"""

    # SSE 不能返回错误状态码（浏览器 EventSource 会停连），统一走流
    def event_stream():
        # 校验状态
        if state.vectordb is None:
            yield _sse("error", {"message": "系统尚未初始化完成，请先上传文档"})
            return

        # 组装 Workflow 节点
        researcher_node = WorkflowNode(
            role="researcher",
            tools=[search_docs],
            prompt=state.researcher_prompt,
            output_key="research",
            output_type="text",
        )
        writer_node = WorkflowNode(
            role="writer",
            tools=[],
            prompt=state.writer_prompt,
            output_key="answer",
        )
        reviewer_node = WorkflowNode(
            role="reviewer",
            tools=[review_result],
            prompt=state.reviewer_prompt,
            output_key="answer",
            output_type="tool",
        )

        workflow = Workflow(
            nodes=[researcher_node, writer_node, reviewer_node],
            llm=state.llm,
        )

        try:
            for event in workflow.stream(question):
                yield _sse(event["event"], event["data"])
        except Exception as e:
            logger.error(f"Workflow stream 异常: {e}")
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    """拼 SSE 格式：event: xxx\ndata: {...}\n\n"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
