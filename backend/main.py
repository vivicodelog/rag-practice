"""
FastAPI 应用入口。

启动时初始化 RAG 组件，然后提供 HTTP 服务。
"""

import sys
import os

from rag_forge.agent.tools import init_tools

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.router import router
from backend.sse import router as sse_router
import backend.state as state

from rag_forge.agent.agent import create_llm
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore, need_rebuild
from rag_forge.data.manifest import sync_manifest


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载模型和构建向量库"""
    logger.info("正在初始化 RAG 系统...")

    sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)

    embeddings = create_embeddings()
    state.embeddings = embeddings
    source = FileSource(settings.DATA_DIR)

    should_rebuild, existing_vdb, _ = need_rebuild(source, settings.SYNC_STATE_FILE)
    if should_rebuild or existing_vdb is None:
        vectordb, all_chunks, _ = build_vectorstore(
            source, embeddings, settings.CHROMA_DIR
        )
    else:
        vectordb = existing_vdb
        chunks_path = os.path.join(settings.CHROMA_DIR, "chunks.json")
        if os.path.exists(chunks_path):
            import json
            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)
        else:
            all_chunks = []

    state.vectordb = vectordb
    state.all_chunks = all_chunks
    logger.info(f"向量库加载完成，共 {len(all_chunks)} 个块")

    llm = create_llm(
        api_key=settings.DEEPSEEK_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )
    state.llm = llm
   

    # 加载 Workflow prompt
    state.researcher_prompt = open(
        os.path.join(settings.PROMPTS_DIR_AGENT, "researcher.md"),
        encoding="utf-8",
    ).read().strip()
    state.writer_prompt = open(
        os.path.join(settings.PROMPTS_DIR_AGENT, "writer.md"),
        encoding="utf-8",
    ).read().strip()
    state.reviewer_prompt = open(
        os.path.join(settings.PROMPTS_DIR_AGENT, "reviewer.md"),
        encoding="utf-8",
    ).read().strip()

    if settings.RERANK_ENABLED:
        try:
            from rag_forge.retrieval.reranker import Reranker
            state.reranker = Reranker()
            logger.info("Reranker 加载完成")
        except Exception as e:
            logger.warning(f"Reranker 加载失败，跳过：{e}")

    logger.info("RAG 系统初始化完成")
    init_tools(state.vectordb, state.all_chunks, state.llm, state.reranker)

    yield  # ← 应用开始接收请求

    # （关停清理放这里，目前不需要）


app = FastAPI(title="RAG-Forge API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(sse_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True) 