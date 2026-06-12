"""
FastAPI 应用入口。

启动时初始化 RAG 组件，然后提供 HTTP 服务。
"""

import sys
import os

from rag_forge.agent.tools import init_tools

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.router import router
import backend.state as state

from rag_forge.agent.agent import create_llm
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore, need_rebuild
from rag_forge.data.manifest import sync_manifest



app = FastAPI(title="RAG-Forge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """启动时加载模型和构建向量库"""
    logger.info("正在初始化 RAG 系统...")

    sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)

    embeddings = create_embeddings()
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
    _prompt_path = os.path.join(settings.PROMPTS_DIR, "chat.md")
    with open(_prompt_path, "r", encoding="utf-8") as _f:
        state.prompts = _f.read().strip()
        

    if settings.RERANK_ENABLED:
        try:
            from rag_forge.retrieval.reranker import Reranker
            state.reranker = Reranker()
            logger.info("Reranker 加载完成")
        except Exception as e:
            logger.warning(f"Reranker 加载失败，跳过：{e}")

    logger.info("RAG 系统初始化完成")
    init_tools(state.vectordb, state.all_chunks, state.llm, state.reranker)


app.include_router(router)
