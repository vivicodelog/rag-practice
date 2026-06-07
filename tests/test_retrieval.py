"""
检索模块的单元测试。

运行方式：
    cd d:/rag-project
    pytest tests/test_retrieval.py -v
"""

import sys
import os

# 把项目根目录加到 Python 路径，才能 import rag_forge
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------- 初始化（只跑一次，所有测试共用）----------
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore

print("正在初始化向量库（首次运行会下载模型，稍等几秒）...")
embeddings = create_embeddings()
source = FileSource(settings.DATA_DIR)
vectordb, all_chunks, _ = build_vectorstore(source, embeddings, settings.CHROMA_DIR)
print(f"初始化完成，共 {len(all_chunks)} 个文档块\n")


# ---------- 测试用例 ----------

from rag_forge.retrieval.vector import vector_search
from rag_forge.retrieval.keyword import keyword_search
from rag_forge.retrieval.hybrid import hybrid_search


def test_vector_returns_list():
    """向量检索应该返回列表，不会报错"""
    results = vector_search("北京", vectordb, top_k=3)
    assert isinstance(results, list)


def test_keyword_finds_match():
    """关键词搜'跨域'应该能搜到结果（java.txt 里有这个词）"""
    results = keyword_search("跨域", all_chunks, top_k=3)
    assert len(results) > 0, "关键词'跨域'应该搜到结果"


def test_hybrid_not_empty():
    """混合检索不应该返回空结果"""
    results = hybrid_search("北京人口", vectordb, all_chunks, top_k=3)
    assert len(results) > 0, "混合检索应该至少返回一条结果"
