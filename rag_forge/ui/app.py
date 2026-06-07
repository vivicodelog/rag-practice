"""
Gradio 用户界面：问答 + 文档管理。

整合 rag_forge 所有模块，拼成可运行的应用程序。
"""
import json
import os
import traceback
from datetime import datetime

import gradio as gr
from loguru import logger

from rag_forge.agent.agent import build_agent, chat, create_llm, system_prompt
from rag_forge.agent.tools import get_weather, init_tools, search_docs
from rag_forge.config import settings
from rag_forge.data.loader import FileSource, build_vectorstore, need_rebuild
from rag_forge.data.manifest import load_manifest, save_manifest, sync_manifest
from rag_forge.embedding.embed import create_embeddings
from rag_forge.retrieval.reranker import Reranker


# ==================== 初始化（模块级别，启动时执行一次）====================

os.makedirs(settings.DATA_DIR, exist_ok=True)
sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)

embeddings = create_embeddings(
    model_path=settings.EMBEDDING_MODEL_PATH,
    device=settings.EMBEDDING_DEVICE,
    normalize=settings.EMBEDDING_NORMALIZE,
)

source = FileSource(settings.DATA_DIR)
should_rebuild, vectordb, old_state = need_rebuild(source, settings.SYNC_STATE_FILE)

if should_rebuild or vectordb is None:
    # 加载旧的 chunks（用于增量合并）
    old_chunks = []
    chunks_path = os.path.join(settings.CHROMA_DIR, "chunks.json")
    if os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            old_chunks = json.load(f)

    vectordb, all_chunks, file_md5s = build_vectorstore(
        source, embeddings, settings.CHROMA_DIR,
        old_state=old_state, old_chunks=old_chunks,
    )
    # 写同步状态（含每个文件的 MD5）
    os.makedirs(os.path.dirname(settings.SYNC_STATE_FILE), exist_ok=True)
    with open(settings.SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "sync_key": source.get_sync_key(),
            "files": file_md5s,
            "updated_at": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
else:
    # 从文件加载 chunks，供关键词搜索使用
    chunks_path = os.path.join(settings.CHROMA_DIR, "chunks.json")
    if os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            all_chunks = json.load(f)
    else:
        all_chunks = []

llm = create_llm(
    api_key=settings.DEEPSEEK_API_KEY,
    model=settings.LLM_MODEL,
    temperature=settings.LLM_TEMPERATURE,
)

# 注入数据 + llm + reranker，供 tools（search_docs 等）使用
if settings.RERANK_ENABLED:
    try:
        logger.info("  加载 Rerank 模型...")
        reranker = Reranker(
            model_name=settings.RERANK_MODEL,
            model_path=settings.RERANK_MODEL_PATH,
        )
        logger.info("  Rerank 模型加载完成")
    except Exception as e:
        logger.info(f"  Rerank 模型加载失败: {e}")
        reranker = None
else:
    reranker = None

init_tools(vectordb, all_chunks, llm=llm, reranker=reranker)

tools = [get_weather, search_docs]

agent = build_agent(llm, tools, system_prompt=system_prompt)


# ==================== 聊天包装 ====================

def chat_fn(message: str, history: list):
    """Gradio ChatInterface 回调，包装 agent.chat"""
    yield from chat(message, history, agent, llm,
                    max_rounds=settings.MAX_HISTORY_ROUNDS)


# ==================== 文档管理函数 ====================

def rebuild_vectorstore():
    """重建向量库并重新注入 tools（上传/删除后调用）"""
    global vectordb, all_chunks
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


def get_document_df():
    """返回文档列表表格"""
    manifest = load_manifest(settings.MANIFEST_FILE)
    if not manifest:
        return [["暂无文档", "", ""]]
    rows = []
    for item in manifest:
        size_kb = item["size"] / 1024
        rows.append([
            item["filename"],
            f"{size_kb:.1f} KB",
            item["upload_date"][:19]
        ])
    return rows


def get_delete_choices():
    """返回文件名列表（供下拉框使用）"""
    return [item["filename"] for item in load_manifest(settings.MANIFEST_FILE)]


def update_delete_dropdown():
    """刷新下拉框，清空选中值"""
    return gr.Dropdown(choices=get_delete_choices(), value=None, interactive=True)


def upload_document(file):
    """保存文件 → 更新清单 → 重建向量库"""
    drop = update_delete_dropdown
    try:
        if file is None:
            return "请选择文件", get_document_df(), drop()

        if isinstance(file, (list, tuple)):
            file = file[0] if file else None
        if file is None:
            return "请选择文件", get_document_df(), drop()

        # Gradio 6 的 UploadButton 传的是路径字符串
        if isinstance(file, str):
            file_path = file
            original_name = os.path.basename(file)
        else:
            file_path = file.path
            original_name = file.orig_name or os.path.basename(file_path)

        filename = original_name
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('txt', 'pdf', 'docx', 'md', 'doc'):
            return "仅支持 TXT、PDF、DOCX、MD 文件", get_document_df(), drop()

        manifest = load_manifest(settings.MANIFEST_FILE)
        if any(item["filename"] == filename for item in manifest):
            return f"文件 '{filename}' 已存在，请先删除旧文件", get_document_df(), drop()

        dest_path = os.path.join(settings.DATA_DIR, filename)
        with open(file_path, "rb") as src, open(dest_path, "wb") as dst:
            dst.write(src.read())

        manifest.append({
            "filename": filename,
            "size": os.path.getsize(dest_path),
            "upload_date": datetime.now().isoformat()
        })
        save_manifest(manifest, settings.MANIFEST_FILE)

        try:
            rebuild_vectorstore()
        except Exception:
            # 重建失败 → 回滚
            if os.path.exists(dest_path):
                os.remove(dest_path)
            manifest = load_manifest(settings.MANIFEST_FILE)
            manifest = [item for item in manifest if item["filename"] != filename]
            save_manifest(manifest, settings.MANIFEST_FILE)
            raise

        return f"✓ 文件 '{filename}' 上传成功，向量库已重建", get_document_df(), drop()
    except Exception as e:
        traceback.print_exc()
        return f"❌ 上传失败：{type(e).__name__}: {e}", get_document_df(), drop()


def delete_document(filename):
    """删除文件 → 更新清单 → 重建向量库"""
    drop = update_delete_dropdown
    try:
        if not filename:
            return get_document_df(), drop(), "请选择要删除的文件"

        manifest = load_manifest(settings.MANIFEST_FILE)
        manifest = [item for item in manifest if item["filename"] != filename]
        save_manifest(manifest, settings.MANIFEST_FILE)

        filepath = os.path.join(settings.DATA_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        rebuild_vectorstore()

        return get_document_df(), drop(), f"✓ 文件 '{filename}' 已删除，向量库已重建"
    except Exception as e:
        traceback.print_exc()
        return get_document_df(), drop(), f"❌ 删除失败：{type(e).__name__}: {e}"


def refresh_list():
    return get_document_df()


# ==================== UI 界面 ====================

CUSTOM_CSS = """
footer {display: none !important;}
.gradio-container {max-width: 900px !important; margin: 0 auto;}
"""


def create_app():
    """构建 Gradio 应用"""
    with gr.Blocks(title="RAG 智能问答 - Forge", css=CUSTOM_CSS) as demo:
        # ---------- Tab 1: 问答 ----------
        with gr.Tab("💬 问答"):
            gr.ChatInterface(
                fn=chat_fn,
                title="📚 RAG 智能问答",
                description="基于 LangChain + DeepSeek + Chroma 的文档问答助手",
            )

        # ---------- Tab 2: 文档管理 ----------
        with gr.Tab("📁 文档管理"):
            gr.Markdown("## 📤 上传文档")
            gr.Markdown("支持 **TXT**、**PDF**、**DOCX** 和 **MD** 格式，上传后自动重建知识库")

            with gr.Row():
                upload_btn = gr.UploadButton(
                    "选择文件上传",
                    file_types=[".txt", ".pdf", ".doc", ".docx", ".md"],
                    file_count="single",
                    variant="primary",
                )
                upload_status = gr.Textbox(
                    label="状态",
                    interactive=False,
                    placeholder="就绪",
                    scale=2,
                )

            gr.Markdown("## 📋 已上传文档")
            doc_list = gr.Dataframe(
                value=get_document_df(),
                headers=["文件名", "大小", "上传时间"],
                datatype=["str", "str", "str"],
                interactive=False,
                label="文档列表",
            )

            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新列表", variant="secondary")

            gr.Markdown("## 🗑️ 删除文档")
            with gr.Row():
                delete_dropdown = gr.Dropdown(
                    label="选择要删除的文档",
                    choices=get_delete_choices(),
                    interactive=True,
                    scale=3,
                )
                delete_btn = gr.Button("删除选中", variant="stop", scale=1)

            # 事件绑定
            upload_btn.upload(
                upload_document,
                upload_btn,
                [upload_status, doc_list, delete_dropdown],
            )

            refresh_btn.click(
                refresh_list, None, doc_list
            ).then(
                update_delete_dropdown, None, delete_dropdown,
            )

            delete_btn.click(
                delete_document,
                delete_dropdown,
                [doc_list, delete_dropdown, upload_status],
            )

    return demo


def main():
    """启动入口"""
    # 配置结构化日志：同时写文件（自动轮转）和终端
    logger.add(
        "rag_forge.log",
        rotation="10 MB",
        retention="30 days",
        level="INFO",
        encoding="utf-8",
    )
    logger.info("RAG-Forge 启动")
    app = create_app()
    app.launch()


if __name__ == "__main__":
    main()
