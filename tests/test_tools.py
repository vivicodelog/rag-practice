"""tests/test_tools.py"""
import pytest
from unittest.mock import MagicMock, patch




class TestSearchDocs:
    """search_docs 工具测试"""

    def test_uninitialized(self):
        """vectordb 为 None 时返回错误提示"""
        from rag_forge.agent.tools import search_docs
        #patch 的原理是：在 with 块内临时把模块里的变量换成你的 mock 值，一退出 with 立刻恢复原样
        with patch("rag_forge.agent.tools._vectordb", None):
            with patch("rag_forge.agent.tools._all_chunks", []):
                result = search_docs.invoke({"query": "rag是什么"})
                assert result == "知识库尚未初始化，请先上传文档"


    @patch("rag_forge.agent.tools.hybrid_search")
    def test_no_results(self, mock_search):
        """检索无结果时返回'未找到相关文档'"""
        from rag_forge.agent.tools import search_docs
        with patch("rag_forge.agent.tools._vectordb", MagicMock()):
            with patch("rag_forge.agent.tools._all_chunks", ["chunk1"]):
                mock_search.return_value = []
                result = search_docs.invoke({"query": "rag是什么"})                
                assert result == "未找到相关文档"

    @patch("rag_forge.agent.tools.hybrid_search")
    def test_low_score(self, mock_search):
        """检索无结果时返回'未找到相关文档'"""
        from rag_forge.agent.tools import search_docs
        with patch("rag_forge.agent.tools._vectordb", MagicMock()):
            with patch("rag_forge.agent.tools._all_chunks", ["chunk1"]):
                mock_search.return_value = [("一些内容", 0.1, "source.txt")]
                result = search_docs.invoke({"query": "rag是什么"})                
                assert result == "未找到相关文档"


class TestQueryDatabase:
    """query_database 测试"""
    @patch("nl2sql.agent.nl2sql")
    def test_error(self, mock_search):
        """vectordb 为 None 时返回错误提示"""
        from rag_forge.agent.tools import query_database   
        mock_search.return_value = {
            "sql": "",
            "columns": [],
            "rows": [],
            "error": "数据库连接失败",
            "explanation": "",
        }
        result = query_database.invoke({"question":"测试"})
        assert result == "数据库连接失败"

    @patch("nl2sql.agent.nl2sql")
    def test_success(self, mock_nl2sql):
        """正常返回时拼成易读文本"""
        from rag_forge.agent.tools import query_database  
        mock_nl2sql.return_value = {
            "sql": "SELECT name FROM authors",
            "columns": ["姓名"],
            "rows": [["鲁迅"], ["老舍"]],
            "error": None,
            "explanation": "查询所有作者姓名",
        }
        result = query_database.invoke({"question": "列出所有作者"})
        # 断言：SQL 在结果里、中文列名在结果里、数据在结果里、解释在结果里
        assert "SELECT name FROM authors" in result
        assert "鲁迅" in result
        assert "查询所有作者姓名" in result

    @patch("nl2sql.agent.nl2sql")
    def test_empty_rows(self, mock_nl2sql):
        """空结果集正常处理"""
        from rag_forge.agent.tools import query_database  
        mock_nl2sql.return_value = {
            "sql": "SELECT name FROM authors WHERE 1=0",
            "columns": ["姓名"],
            "rows": [],
            "error": None,
            "explanation": "无匹配数据",
        }
        result = query_database.invoke({"question": "查询不存在的内容"})
        assert "SQL:" in result
        assert "数据：" in result

class TestRewriteQuery:
    """rewrite_query 测试"""
    def test_short_with_llm(self):
        """短查询用 LLM 重写"""
        from rag_forge.agent.tools import _rewrite_query
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "今天北京天气怎么样"   # 设 .content 为字符串
        mock_llm.invoke.return_value = mock_response   # invoke() 返回 mock_response

        with patch("rag_forge.agent.tools._llm", mock_llm):
            result = _rewrite_query("北京天气")
            assert result == "今天北京天气怎么样"


    def test_long_skipped(self):
        """长查询（>10字）跳过 LLM 扩展"""
        from rag_forge.agent.tools import _rewrite_query
        
        mock_llm = MagicMock()
        with patch("rag_forge.agent.tools._llm", mock_llm):
            result = _rewrite_query("今天北京的天气怎么样啊")
            assert result == "今天北京的天气怎么样啊"      # 原样返回
            mock_llm.invoke.assert_not_called()  # 验证确实没调 LLM


    def test_no_llm(self):
        """_llm 为 None 时跳过"""
        from rag_forge.agent.tools import _rewrite_query
        with patch("rag_forge.agent.tools._llm", None):
            result = _rewrite_query("天气")
            assert result == "天气"










