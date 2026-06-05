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

def build_vectorstore(source: BaseSource, embeddings, persist_dir: str):
    """
    从数据源读取文档 → 切分 → 存入 Chroma 向量库。

    参数:
        source: BaseSource 子类实例（如 FileSource）
        embeddings: 嵌入模型
        persist_dir: Chroma 持久化目录

    返回:
        (vectordb, all_chunks)
        vectordb: Chroma 实例
        all_chunks: 所有文本块列表，格式 [{"content": str, "metadata": dict}]
    """
    #   1. source.get_documents() 获取原始文档
    #   2. RecursiveCharacterTextSplitter 切分（chunk_size=300, overlap=30）
    #   3. Chroma.from_documents() 存入向量库
    #   4. 保存 chunks.json 供关键词搜索使用
    #   5. 返回 (vectordb, all_chunks)
    #
    # 提示：从 rag_app.py 的 build_vectorstore() 复制
    logger.info("加载文档...")
    raw_docs = source.get_documents()#获取所有文档
    if not raw_docs:
        raise Exception("没有找到任何文档")
    logger.info("切分文档...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    all_chunks = []
    for doc_id, text, meta in raw_docs:#参数（doc_id = "报告.pdf::报告内容前50字..."、text = "完整的报告内容..."、meta = {"source": "报告.pdf"}）
        chunks = text_splitter.split_text(text)
        for i, chunk in enumerate(chunks):#enumerate() 的作用： 同时获取索引和值
            all_chunks.append((f"{doc_id}::chunks{i}", chunk, {**meta, "doc_id": doc_id}))
            #追溯到原始文档，每个块都有唯一ID，知道是文档的第几个块     
           
    logger.info(f"  切分为 {len(all_chunks)} 个片段")

    docs = [Document(page_content=c, metadata=m) for _, c, m in all_chunks]
    chunks_dict = [{"content": d.page_content, "metadata": d.metadata} for d in docs]

    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir,
    )

    chunks_path = os.path.join(persist_dir, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks_dict, f, ensure_ascii=False, indent=2)
    logger.info("向量数据库构建完成")
    return vectordb, chunks_dict

def need_rebuild(source: BaseSource, sync_state_file: str):
    """
    检查文档是否有变化，决定是否重建。

    比较 source.get_sync_key() 和 sync_state_file 中保存的 sync_key。
    同时兜底检测向量库存不存在。

    返回:
        (should_rebuild: bool, vectordb_or_None)
    """
    #   1. 计算 source.get_sync_key()
    #   2. 加载 sync_state_file 中的旧 sync_key
    #   3. 如果一致且向量库文件存在 → 加载现有 Chroma → 返回 (False, vectordb)
    #   4. 否则 → 返回 (True, None)
    #
    # 提示：从 rag_app.py 的 need_rebuild() + vectordb_from_existing() 复制
    current_key = source.get_sync_key()
    old_state = {}
    if os.path.exists(sync_state_file):
        with open(sync_state_file, "r", encoding="utf-8") as f:
            old_state = json.load(f)
    if old_state.get("sync_key") == current_key:
        logger.info("  文档无变化，跳过重建")
        # 尝试加载现有向量库
        persist_dir = os.path.dirname(sync_state_file)
        if os.path.exists(os.path.join(persist_dir, "chroma.sqlite3")):
            from langchain_chroma import Chroma
            from rag_forge.embedding.embed import create_embeddings
            vectordb = Chroma(
                embedding_function=create_embeddings(),
                persist_directory=persist_dir,
            )
            return False, vectordb
        return False, None
    logger.info("  检测到文档变化，重建向量库...")
    return True, None

