"""
Reranker 重排序的单元测试。

注意：如果模型还没下载，首次运行会下载 ~1GB 模型，需要稍等。
如果不想等，可以跳过这个文件：
    pytest tests/ -v --ignore=tests/test_reranker.py

运行：
    pytest tests/test_reranker.py -v
"""


def test_reranker_import():
    """基本功能：Reranker 类可以正常导入"""
    from rag_forge.retrieval.reranker import Reranker

    assert Reranker is not None
    assert hasattr(Reranker, "rerank"), "Reranker 应该有 rerank 方法"


def test_reranker_instantiation():
    """实例化：能创建 Reranker 实例（如果模型已缓存则快速通过）"""
    from rag_forge.retrieval.reranker import Reranker

    try:
        reranker = Reranker()
        assert reranker is not None
        assert reranker.model is not None, "模型应该加载成功"
    except Exception as e:
        import pytest
        pytest.skip(f"模型加载失败（首次使用需要下载）：{e}")


def test_reranker_rerank_returns_correct_format():
    """rerank 方法：返回格式应为 [(content, score, source)]"""
    from rag_forge.retrieval.reranker import Reranker

    try:
        reranker = Reranker()
    except Exception as e:
        import pytest
        pytest.skip(f"模型加载失败，跳过：{e}")

    candidates = [
        ("北京是中国的首都", 0.5, "test.txt"),
        ("上海是中国的金融中心", 0.4, "test.txt"),
        ("广州是南方城市", 0.3, "test.txt"),
    ]
    results = reranker.rerank("北京", candidates, top_k=2)

    assert isinstance(results, list), "rerank 应该返回列表"
    assert len(results) <= 2, "top_k=2 最多返回 2 条"

    for item in results:
        assert len(item) == 3, f"每条结果应该是三元组：{item}"
        assert isinstance(item[0], str), "content 应该是字符串"
        assert isinstance(item[1], float), "score 应该是浮点数"
        assert isinstance(item[2], str), "source 应该是字符串"
