"""
API 路由。

核心就是调 rag_forge 的函数。
"""

import os
from fastapi import APIRouter, HTTPException
from loguru import logger

from rag_forge.config import settings
from rag_forge.retrieval.hybrid import hybrid_search
from rag_forge.data.manifest import sync_manifest

import backend.state as state
from backend.schemas import ChatRequest, ChatResponse, SourceItem

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """问答接口：接收问题，返回回答和来源"""
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    try:
        results = hybrid_search(
            query=request.question,
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
            for c, score, s in results
        ]
      
        context_text = "\n---\n".join([c for c, s, src in results])
        prompt= state.prompts.replace("{context}", context_text).replace("{question}", request.question)
        answer = state.llm.invoke(prompt).content
        return ChatResponse(
            answer=answer,
            sources=sources,
        )
    except Exception as e:
        logger.error(f"聊天接口异常：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
def list_documents():
    """列出所有文档"""
    manifest = sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)
    filenames = [item["filename"] for item in manifest]
    return {"documents": filenames}


@router.get("/health")
def health():
    """健康检查"""
    return {
        "status": "ok",
        "vectordb": state.vectordb is not None,
        "chunks": len(state.all_chunks),
        "reranker": state.reranker is not None,
    }
