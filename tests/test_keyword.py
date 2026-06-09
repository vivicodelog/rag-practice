"""
关键词检索的单元测试。

关键词检索不需要加载嵌入模型，跑得很快。

运行：
    pytest tests/test_keyword.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------- 初始化 ----------
from rag_forge.config import settings
from rag_forge.data.loader import FileSource  # 需要用 FileSource 加载 chunks

print("正在加载文档块...")
source = FileSource(settings.DATA_DIR)
from rag_forge.data.loader import build_vectorstore
from rag_forge.embedding.embed import create_embeddings
embeddings = create_embeddings()
vectordb, all_chunks, _ = build_vectorstore(source, embeddings, settings.CHROMA_DIR)
print(f"加载完成，共 {len(all_chunks)} 个块\n")

from rag_forge.retrieval.keyword import keyword_search


def test_keyword_returns_list():
    """基本功能：检索结果应该是一个列表"""
    results = keyword_search("跨域", all_chunks, top_k=3)
    assert isinstance(results, list)


def test_keyword_finds_exact_match():
    """精准匹配：'跨域' 应该能在 java.txt 中找到"""
    results = keyword_search("跨域", all_chunks, top_k=5)
    # keyword_search 返回 (score, content, source) 格式
    contents = "".join(c for _, c, _ in results)
    #                        ↑     ↑  ↑
    #                     分数 内容 来源 — 只要中间的"内容"，用 _ 忽略其他
    #搜出来一堆结果，把它们的内容拼到一起，看看"跨域"这个词到底在不在里面
    assert "跨域" in contents, "关键词 '跨域' 应出现在结果中"


def test_keyword_score_range():
    """分数范围：score 应该在 0~1 之间"""
    results = keyword_search("跨域", all_chunks, top_k=3)
    for score, _, _ in results:
        assert 0 <= score <= 1, f"分数 {score} 超出范围"


def test_keyword_empty_for_nonsense():
    """健壮性：乱码关键词应返回空列表（没有词能匹配）"""
    results = keyword_search("xxxxxyyyyyzzzzz", all_chunks, top_k=3)
    assert len(results) == 0, f"乱码应该没有匹配，实际返回 {len(results)} 条"


def test_keyword_scored_higher_for_more_matches():
    """排序：匹配更多关键词的结果分数应该更高"""
    results = keyword_search("跨域", all_chunks, top_k=5)
    if len(results) >= 2:
        # keyword_search 返回 (score, content, source)，score 在 [0] 位
        assert results[0][0] >= results[1][0], "结果应该按分数降序排列"#返回数据是元组不是数组类型
