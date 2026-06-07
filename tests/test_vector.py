"""
向量检索的单元测试。

运行：
    pytest tests/test_vector.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------- 初始化（所有测试用例共用）----------
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore

print("正在初始化向量库...")
embeddings = create_embeddings()
source = FileSource(settings.DATA_DIR)
vectordb, all_chunks, _ = build_vectorstore(source, embeddings, settings.CHROMA_DIR)
print(f"初始化完成，共 {len(all_chunks)} 个块\n")

from rag_forge.retrieval.vector import vector_search


def test_vector_returns_list():
    """基本功能：检索结果应该是一个列表"""
    results = vector_search("北京", vectordb, top_k=3)
    assert isinstance(results, list)


def test_vector_score_between_0_and_1():
    """分数归一化：每条结果的 score 应该在 0~1 之间"""
    results = vector_search("北京", vectordb, top_k=5)
    for score, _, _ in results:  # _ 表示不关心这个字段
        assert 0 <= score <= 1, f"分数 {score} 超出范围"


def test_vector_result_has_three_fields():
    """结果格式：每条结果应该是 (score, content, source) 三元组"""
    results = vector_search("北京", vectordb, top_k=3)
    for item in results:
        assert len(item) == 3, f"格式错误：{item}"
        assert isinstance(item[0], float), "score 应该是浮点数"
        assert isinstance(item[1], str), "content 应该是字符串"


def test_vector_respects_top_k():
    """参数生效：top_k=2 应该最多返回 2 条"""
    results = vector_search("北京", vectordb, top_k=2)
    assert len(results) <= 2, f"期望 ≤2，实际 {len(results)}"


def test_vector_empty_query_does_not_crash():
    """健壮性：空字符串查询不应该报错"""
    try:
        results = vector_search("", vectordb, top_k=3)
        assert isinstance(results, list)
    except Exception as e:
        assert False, f"空查询抛异常：{e}"
