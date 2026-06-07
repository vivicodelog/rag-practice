"""
文档加载与智能切分。

采用 BaseSource 抽象设计，支持多数据源（文件、数据库等）。
"""
import hashlib
import json
import os

from langchain_chroma import Chroma
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from rag_forge.config import settings



# ==================== 数据源抽象层 ====================

class BaseSource:
    """数据源基类。所有数据源继承这个类。"""

    directory: str = ""  # 子类（FileSource）覆盖此值

    def get_documents(self):
        """返回 [(doc_id, text, metadata)]"""
        raise NotImplementedError

    def get_sync_key(self):
        """返回 MD5 指纹，用于检测数据是否有变化"""
        raise NotImplementedError


class FileSource(BaseSource):
    """从本地文件夹读取文档。"""

    def __init__(self, directory: str):
        self.directory = directory

    def get_documents(self):
        """
        遍历目录，按扩展名选 Loader 加载文档。

        支持的格式：txt, pdf, docx, md
        返回 [(doc_id, text, metadata)]
        """
        # 从 rag_app.py 复制 FileSource.get_documents() 代码
        # 注意把硬编码的 DATA_DIR 换成 self.directory
        docs = []#存放的所有文档
        for fname in os.listdir(self.directory):
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if ext not in ('txt', 'pdf', 'docx', 'md'):
                continue
            path = os.path.join(self.directory, fname)#获取完整路径把文件夹路径和文件名拼接到一起，形成完整的文件路径
            if not os.path.isfile(path):
                continue
            if ext == "txt":
                loader = TextLoader(path, encoding="utf-8")
            elif ext == "pdf":
                loader = PyPDFLoader(path)
            elif ext == "docx":
                loader = Docx2txtLoader(path)
            elif ext in ("md", "markdown"):
                loader = UnstructuredMarkdownLoader(path)
            else:
                continue  # 不支持的格式跳过
            loaded = loader.load()#加载文档内容，加载文档块
            for doc in loaded:
                doc_id = fname + "::" + doc.page_content[:50]
                docs.append((doc_id, doc.page_content, {"source": path}))
            print(f"  {fname} 加载成功")
        return docs

    def get_sync_key(self):
        """
        计算所有文件的 MD5 合值，用于检测变化。

        遍历目录 → 计算每个文件的 MD5 → 拼接 → 再算一次 MD5
        """
        # 从 rag_app.py 复制 FileSource.get_sync_key() 代码
        combined = ""
        for fname in sorted(os.listdir(self.directory)):
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if ext not in ('txt', 'pdf', 'docx', 'md'):
                continue
            path = os.path.join(self.directory, fname)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    combined += hashlib.md5(f.read()).hexdigest()
        return hashlib.md5(combined.encode()).hexdigest()#双层的加密


class DatabaseSource(BaseSource):
    """数据库数据源（待实现）。

    预留类，以后可以支持从 MySQL/PostgreSQL 查询数据。
    """

    def __init__(self, connection_string: str, query: str):
        self.connection_string = connection_string
        self.query = query

    def get_documents(self):
        raise NotImplementedError

    def get_sync_key(self):
        raise NotImplementedError


# ==================== 向量库构建 ====================

def get_file_md5s(directory: str) -> dict:
    """
    计算 data/ 下每个文件的 MD5，返回 {filename: md5}。

    用于增量更新：对比新旧 MD5，就知道哪些文件变了。
    """
    file_md5s = {}
    for fname in os.listdir(directory):
        ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
        if ext not in ('txt', 'pdf', 'docx', 'md'):
            continue
        path = os.path.join(directory, fname)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                file_md5s[fname] = hashlib.md5(f.read()).hexdigest()
    return file_md5s


def build_vectorstore(source: BaseSource, embeddings, persist_dir: str,
                       old_state: dict | None = None,
                       old_chunks: list | None = None):
    """
    构建向量库（支持全量 / 增量两种模式）。

    参数:
        source: 数据源
        embeddings: 嵌入模型
        persist_dir: Chroma 持久化目录
        old_state: sync_state.json 的旧内容（含 per-file MD5）
                   = None → 全量构建
                   ≠ None → 增量构建
        old_chunks: 旧的 chunks.json 内容（增量时保留没变的部分）

    返回:
        (vectordb, all_chunks, file_md5s)
    """
    raw_docs = source.get_documents()
    if not raw_docs:
        raise Exception("没有找到任何文档")

    # ---- 增量模式：找出新增/修改/删除的文件 ----
    current_md5s = get_file_md5s(source.directory)
    changed_files = set()

    if old_state is not None and "files" in old_state:
        old_md5s = old_state["files"]
        for fname, md5 in current_md5s.items():
            if fname not in old_md5s or old_md5s[fname] != md5:
                changed_files.add(fname)
        for fname in old_md5s:
            if fname not in current_md5s:
                changed_files.add(fname)

        if not changed_files:
            # 没有变化，直接加载现有的
            vectordb = Chroma(
                embedding_function=embeddings,
                persist_directory=persist_dir,
            )
            logger.info("  文档无变化，跳过重建")
            return vectordb, (old_chunks or []), current_md5s

        logger.info(f"  检测到 {len(changed_files)} 个文件变化，增量更新...")

    # ---- 切分文档 ----
    logger.info("切分文档...")
    all_chunks = []
    for doc_id, text, meta in raw_docs:
        filename = os.path.basename(meta["source"])

        # 增量模式下，没变化的文件跳过
        if old_state is not None and filename not in changed_files:
            continue

        splitter = get_splitter(filename)
        chunks = splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append((f"{doc_id}::chunk{i}", chunk, {**meta, "doc_id": doc_id}))

    logger.info(f"  切分为 {len(all_chunks)} 个片段")

    docs = [Document(page_content=c, metadata=m) for _, c, m in all_chunks]
    new_chunks_dict = [{"content": d.page_content, "metadata": d.metadata} for d in docs]

    if old_state is not None and os.path.exists(os.path.join(persist_dir, "chroma.sqlite3")):
        # ======== 增量模式：删除旧的 + 添加新的 ========
        vectordb = Chroma(
            embedding_function=embeddings,
            persist_directory=persist_dir,
        )

        # 1. 从 Chroma 删除已删除/修改文件的旧 chunks
        for fname in changed_files:
            file_path = os.path.join(source.directory, fname)
            try:
                # ChromaDB 原生支持按 metadata 过滤删除
                vectordb._collection.delete(where={"source": file_path})
                logger.info(f"  删除旧块: {fname}")
            except Exception:
                pass  # 文件可能不在 Chroma 里

        # 2. 添加新 chunks
        if docs:
            vectordb.add_documents(docs)

        # 3. 合并 chunks.json：保留没变的部分 + 新增的部分
        merged_chunks = []
        if old_chunks:
            for c in old_chunks:
                src = c.get("metadata", {}).get("source", "")
                fname = os.path.basename(src)
                if fname not in changed_files:
                    merged_chunks.append(c)
        merged_chunks.extend(new_chunks_dict)

    else:
        # ======== 全量模式：从头创建 ========
        vectordb = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            persist_directory=persist_dir,
        )
        merged_chunks = new_chunks_dict

    # 保存 chunks.json
    chunks_path = os.path.join(persist_dir, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(merged_chunks, f, ensure_ascii=False, indent=2)
    logger.info(f"向量数据库构建完成（共 {len(merged_chunks)} 个块）")
    return vectordb, merged_chunks, current_md5s


def need_rebuild(source: BaseSource, sync_state_file: str):
    """
    检查文档是否有变化，决定是否重建。

    返回:
        (should_rebuild: bool, vectordb_or_None, old_state: dict)
        old_state 包含旧的文件 MD5 和 chunks，用于增量更新。
    """
    current_key = source.get_sync_key()
    old_state = {}
    if os.path.exists(sync_state_file):
        with open(sync_state_file, "r", encoding="utf-8") as f:
            old_state = json.load(f)

    if old_state.get("sync_key") == current_key:
        logger.info("  文档无变化，跳过重建")
        persist_dir = os.path.dirname(sync_state_file)
        if os.path.exists(os.path.join(persist_dir, "chroma.sqlite3")):
            from rag_forge.embedding.embed import create_embeddings
            vectordb = Chroma(
                embedding_function=create_embeddings(),
                persist_directory=persist_dir,
            )
            return False, vectordb, old_state
        return False, None, old_state

    logger.info("  检测到文档变化，重建向量库...")
    return True, None, old_state

def get_splitter(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "md":
        from langchain_text_splitters import MarkdownHeaderTextSplitter
        return MarkdownHeaderTextSplitter(headers_to_split_on=[("##", "章节")])
    elif ext == "pdf":
        return RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    else:  # txt, docx, 代码等
        return RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)