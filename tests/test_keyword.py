"""
关键词检索的单元测试。

关键词检索不需要加载嵌入模型，跑得很快。

运行：
    pytest tests/test_keyword.py -v
"""

from rag_forge.retrieval.keyword import keyword_search


def test_keyword_returns_list(all_chunks):
    """基本功能：检索结果应该是一个列表"""
    results = keyword_search("跨域", all_chunks, top_k=3)
    assert isinstance(results, list)


def test_keyword_finds_exact_match(all_chunks):
    """精准匹配：'跨域' 应该能在 java.txt 中找到"""
    results = keyword_search("跨域", all_chunks, top_k=5)
    contents = "".join(c for _, c, _ in results)
    assert "跨域" in contents, "关键词 '跨域' 应出现在结果中"


def test_keyword_score_range(all_chunks):
    """分数范围：score 应该在 0~1 之间"""
    results = keyword_search("跨域", all_chunks, top_k=3)
    for score, _, _ in results:
        assert 0 <= score <= 1, f"分数 {score} 超出范围"


def test_keyword_empty_for_nonsense(all_chunks):
    """健壮性：乱码关键词应返回空列表（没有词能匹配）"""
    results = keyword_search("xxxxxyyyyyzzzzz", all_chunks, top_k=3)
    assert len(results) == 0, f"乱码应该没有匹配，实际返回 {len(results)} 条"


def test_keyword_scored_higher_for_more_matches(all_chunks):
    """排序：匹配更多关键词的结果分数应该更高"""
    results = keyword_search("跨域", all_chunks, top_k=5)
    if len(results) >= 2:
        assert results[0][0] >= results[1][0], "结果应该按分数降序排列"
