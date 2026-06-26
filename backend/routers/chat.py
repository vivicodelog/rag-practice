"""Agent / Workflow 聊天路由"""

import os
from fastapi import APIRouter, HTTPException
from loguru import logger

from rag_forge.history import trim_history
from rag_forge.agent.workflow import Workflow, WorkflowNode
from rag_forge.agent.agent import system_prompt
from rag_forge.agent.tools import get_weather, query_database, review_result, search_docs
from rag_forge.config import settings
from rag_forge.retrieval.hybrid import hybrid_search

import backend.state as state
from backend.schemas import ChatRequest, ChatResponse, SourceItem, WorkflowResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """问答接口：Agent 模式，LLM 自主选择工具"""
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    try:
        llm_with_tools = state.llm.bind_tools([get_weather, search_docs, query_database])
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        trimmed = trim_history(request.history or [], state.llm, settings.MAX_HISTORY_ROUNDS)
        for msg in trimmed:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                messages.append(SystemMessage(content=msg["content"]))

        messages.append(HumanMessage(content=request.question))
        sources = []

        for _ in range(3):
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            if not response.tool_calls:
                break
            for tool_call in response.tool_calls:
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
                            SourceItem(
                                filename=os.path.basename(s) if s else "未知",
                                score=score,
                                content=c[:200],
                            )
                            for c, score, s in raw
                        ]
                elif tool_name == "get_weather":
                    result = get_weather.invoke(tool_args)
                elif tool_name == "query_database":
                    result = query_database.invoke(tool_args)
                else:
                    result = f"未知工具：{tool_name}"
                messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

        answer = messages[-1].content if isinstance(messages[-1].content, str) else ""
        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"聊天接口异常：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/workflow", response_model=WorkflowResponse)
def chat_workflow(request: ChatRequest):
    """Workflow 编排：Researcher → Writer → Reviewer"""
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    researcher_prompt = state.researcher_prompt
    writer_prompt = state.writer_prompt
    reviewer_prompt = state.reviewer_prompt

    researcher_node = WorkflowNode(
        role="researcher",
        tools=[search_docs],
        prompt=researcher_prompt,
        output_key="research",
        output_type="text",
    )
    writer_node = WorkflowNode(
        role="writer",
        tools=[],
        prompt=writer_prompt,
        output_key="answer",
    )
    reviewer_node = WorkflowNode(
        role="reviewer",
        tools=[review_result],
        prompt=reviewer_prompt,
        output_key="review",
        output_type="tool",
    )
    nodes = [researcher_node, writer_node, reviewer_node]

    trimmed = trim_history(request.history or [], state.llm, settings.MAX_HISTORY_ROUNDS)
    workflow = Workflow(nodes=nodes, llm=state.llm, history=trimmed)
    result = workflow.run(request.question)
    return WorkflowResponse(answer=result["answer"], steps=result["steps"])
