"""
混合检索的单元测试。

运行：
    pytest tests/test_hybrid.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------- 初始化 ----------
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore

print("正在初始化...")
embeddings = create_embeddings()
source = FileSource(settings.DATA_DIR)
vectordb, all_chunks, _ = build_vectorstore(source, embeddings, settings.CHROMA_DIR)
print(f"初始化完成，共 {len(all_chunks)} 个块\n")

from rag_forge.retrieval.hybrid import hybrid_search


def test_hybrid_returns_list():
    """基本功能：检索结果应该是一个列表"""
    results = hybrid_search("北京人口", vectordb, all_chunks, top_k=3)
    assert isinstance(results, list)


def test_hybrid_not_empty():
    """基本功能：正常查询不应该返回空"""
    results = hybrid_search("北京人口", vectordb, all_chunks, top_k=3)
    assert len(results) > 0, "混合检索应该至少返回一条结果"


def test_hybrid_result_format():
    """结果格式：每条结果应该是 (content, score, source) 三元组"""
    results = hybrid_search("北京人口", vectordb, all_chunks, top_k=3)
    for item in results:
        assert len(item) == 3, f"格式错误：{item}"
        assert isinstance(item[0], str), "content 应该是字符串"
        assert isinstance(item[1], float), "score 应该是浮点数"
        assert isinstance(item[2], str), "source 应该是字符串"


def test_hybrid_respects_top_k():
    """参数生效：top_k 应该被尊重"""
    results = hybrid_search("北京人口", vectordb, all_chunks, top_k=2)
    assert len(results) <= 2


def test_hybrid_returns_more_than_vector_alone():
    """混合优势：混合检索应该比纯向量检索结果更丰富"""
    from rag_forge.retrieval.vector import vector_search

    hybrid_results = hybrid_search("跨域", vectordb, all_chunks, top_k=5)
    vector_results = vector_search("跨域", vectordb, top_k=5)

    # 混合检索因为加了关键词匹配，结果数应该 >= 纯向量检索
    assert len(hybrid_results) >= len(vector_results), (
        f"混合检索 {len(hybrid_results)} 条应 >= 向量检索 {len(vector_results)} 条"
    )
