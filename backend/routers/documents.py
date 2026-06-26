"""文档管理路由"""

from datetime import datetime
import os
import traceback
from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger

from rag_forge.config import settings
from rag_forge.data.manifest import load_manifest, save_manifest, sync_manifest
from rag_forge.service import rebuild_vectorstore

import backend.state as state

router = APIRouter(tags=["documents"])


@router.get("/documents")
def list_documents():
    """列出所有文档"""
    manifest = sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)
    filenames = [item["filename"] for item in manifest]
    return {"documents": filenames}


@router.get("/documents/details")
def list_documents_detail():
    """返回文档列表表格"""
    manifest = load_manifest(settings.MANIFEST_FILE)
    if not manifest:
        return []
    rows = []
    for item in manifest:
        size_kb = item["size"] / 1024
        rows.append({
            "filename": item["filename"],
            "size": f"{size_kb:.1f} KB",
            "upload_time": item["upload_date"][:19]
        })
    return {"documents": rows}


@router.get("/health")
def health():
    """健康检查"""
    return {
        "status": "ok",
        "vectordb": state.vectordb is not None,
        "chunks": len(state.all_chunks),
        "reranker": state.reranker is not None,
    }


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """保存文件 → 更新清单 → 重建向量库"""
    try:
        if file is None:
            return "请选择文件"
        if file.filename is None:
            raise HTTPException(400, detail="上传文件名称为空")

        original_name = file.filename
        file_path = os.path.join(settings.DATA_DIR, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        filename = original_name
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('txt', 'pdf', 'docx', 'md', 'doc'):
            return "仅支持 TXT、PDF、DOCX、MD 文件"

        manifest = load_manifest(settings.MANIFEST_FILE)
        if any(item["filename"] == filename for item in manifest):
            return f"文件 '{filename}' 已存在，请先删除旧文件"

        manifest.append({
            "filename": filename,
            "size": os.path.getsize(file_path),
            "upload_date": datetime.now().isoformat()
        })
        save_manifest(manifest, settings.MANIFEST_FILE)

        try:
            state.vectordb, state.all_chunks = rebuild_vectorstore(state.embeddings)
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            manifest = load_manifest(settings.MANIFEST_FILE)
            manifest = [item for item in manifest if item["filename"] != filename]
            save_manifest(manifest, settings.MANIFEST_FILE)
            raise

        return f"✓ 文件 '{filename}' 上传成功，向量库已重建"
    except Exception as e:
        traceback.print_exc()
        return f"❌ 上传失败：{type(e).__name__}: {e}"


@router.delete("/delete")
def delete_document(filename: str):
    """删除文档并重建向量库"""
    try:
        if not filename:
            return "请选择要删除的文件"
        filepath = os.path.join(settings.DATA_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        state.vectordb, state.all_chunks = rebuild_vectorstore(state.embeddings)
        return f"✓ 文件 '{filename}' 已删除，向量库已重建"
    except Exception as e:
        traceback.print_exc()
        return f"❌ 删除失败：{type(e).__name__}: {e}"


@router.get("/delete/choices")
def get_delete_choices():
    """返回文件名列表（供下拉框使用）"""
    return [item["filename"] for item in load_manifest(settings.MANIFEST_FILE)]
