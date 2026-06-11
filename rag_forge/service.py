"""
业务编排层。

组装底层模块完成完整流程（重建向量库、同步清单等），
供 Gradio UI 和 FastAPI 路由共同调用。
"""

import json
import os
from datetime import datetime

from rag_forge.agent.tools import init_tools
from rag_forge.config import settings
from rag_forge.data.loader import FileSource, build_vectorstore
from rag_forge.data.manifest import sync_manifest


def rebuild_vectorstore(embeddings):
    """
    重建向量库并重新注入 tools（上传/删除后调用）。

    Parameters
    ----------
    embeddings : 嵌入模型实例，由调用方传入（Gradio 版传模块级变量，FastAPI 版传 state.embeddings）

    Returns
    -------
    (vectordb, all_chunks)
    """
    sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)
    s = FileSource(settings.DATA_DIR)

    # 加载旧的 state 和 chunks（用于增量更新）
    old_state = {}
    old_chunks = []
    if os.path.exists(settings.SYNC_STATE_FILE):
        with open(settings.SYNC_STATE_FILE, "r", encoding="utf-8") as f:
            old_state = json.load(f)
    chunks_path = os.path.join(settings.CHROMA_DIR, "chunks.json")
    if os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            old_chunks = json.load(f)

    vectordb, all_chunks, file_md5s = build_vectorstore(
        s, embeddings, settings.CHROMA_DIR,
        old_state=old_state, old_chunks=old_chunks,
    )
    init_tools(vectordb, all_chunks)

    os.makedirs(os.path.dirname(settings.SYNC_STATE_FILE), exist_ok=True)
    with open(settings.SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "sync_key": s.get_sync_key(),
            "files": file_md5s,
            "updated_at": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    return vectordb, all_chunks
