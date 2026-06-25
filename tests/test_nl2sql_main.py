"""
NL2SQL 主逻辑单元测试。

测试策略：
    mock 数据库（内存 SQLite） + mock LLM（MagicMock），
    不碰真实数据库和真实 API。
"""

import sqlite3
import sys
sys.path.insert(0, "d:/rag-project")

from unittest.mock import MagicMock, patch
from nl2sql.agent import nl2sql


def _build_test_db() -> sqlite3.Connection:
    """建一个带测试数据的 SQLite 内存库，返回连接。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE authors (
            author_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT,
            birth_year INTEGER
        );
        CREATE TABLE books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            price REAL,
            stock INTEGER,
            category TEXT
        );
        CREATE TABLE column_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            UNIQUE(table_name, column_name)
        );
        INSERT INTO authors VALUES (1, '鲁迅', '中国', 1881);
        INSERT INTO authors VALUES (2, '老舍', '中国', 1899);
        INSERT INTO authors VALUES (3, 'J.K. Rowling', '英国', 1965);
        INSERT INTO books VALUES (1, '呐喊', 1, 29.0, 100, '小说');
        INSERT INTO books VALUES (2, '彷徨', 1, 32.0, 50, '小说');
        INSERT INTO books VALUES (3, '骆驼祥子', 2, 35.0, 80, '小说');
        INSERT INTO books VALUES (4, 'Harry Potter', 3, 45.0, 200, '外文');
        INSERT INTO column_meta VALUES (1, 'authors', 'name', '姓名');
        INSERT INTO column_meta VALUES (2, 'authors', 'country', '国家');
        INSERT INTO column_meta VALUES (3, 'books', 'title', '书名');
        INSERT INTO column_meta VALUES (4, 'books', 'price', '价格');
        INSERT INTO column_meta VALUES (5, 'books', 'stock', '库存');
    """)
    cursor.close()
    return conn


def test_nl2sql_success(mocker):
    """正常流程：LLM 生成 SQL → 执行 → 返回中文列名 + 解释。"""
    conn = _build_test_db()

    # mock 数据库连接
    mocker.patch("nl2sql.agent.get_connection", return_value=conn)
    mocker.patch("nl2sql.agent.close")                      # close 变空操作

    # mock LLM
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SELECT name FROM authors"
    mock_llm.invoke.return_value = mock_response
    mocker.patch("nl2sql.agent.create_llm", return_value=mock_llm)

    result = nl2sql("列出所有作者")

    # LLM 被调了 2 次：一次生成 SQL，一次解释 SQL
    assert mock_llm.invoke.call_count == 2
    # 返回的 SQL 不含反引号
    assert "SELECT" in result["sql"]
    # 列名被转成中文
    assert result["columns"] == ["姓名"]
    # 有数据
    assert len(result["rows"]) == 3
    # 没错误
    assert result["error"] is None
    # 有解释
    assert result["explanation"] is not None


def test_nl2sql_self_heal(mocker):
    """自愈循环：第一次 SQL 报错，第二次 LLM 重试后成功。"""
    conn = _build_test_db()

    mocker.patch("nl2sql.agent.get_connection", return_value=conn)
    mocker.patch("nl2sql.agent.close")

    mock_llm = MagicMock()
    # 第一次返回错误 SQL（不存在的列）
    bad_response = MagicMock()
    bad_response.content = "SELECT nonexistent FROM authors"
    # 第二次返回正确 SQL
    good_response = MagicMock()
    good_response.content = "SELECT name FROM authors"
    # side_effect 让每次 invoke 返回不同结果
    mock_llm.invoke.side_effect = [bad_response, good_response, good_response]
    mocker.patch("nl2sql.agent.create_llm", return_value=mock_llm)

    result = nl2sql("列出所有作者")

    assert result["error"] is None
    assert len(result["rows"]) == 3
    # 至少调了 2 次 LLM（生成 SQL）
    assert mock_llm.invoke.call_count >= 2


def test_nl2sql_with_history(mocker):
    """带历史对话时，prompt 应包含历史内容。"""
    conn = _build_test_db()

    mocker.patch("nl2sql.agent.get_connection", return_value=conn)
    mocker.patch("nl2sql.agent.close")

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SELECT name FROM authors"
    mock_llm.invoke.return_value = mock_response
    mocker.patch("nl2sql.agent.create_llm", return_value=mock_llm)

    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮你的"},
    ]
    result = nl2sql("列出所有作者", history=history)

    assert result["error"] is None
    # 验证历史被传进了第一次 invoke 的 prompt（生成 SQL 的那次）
    prompt_arg = mock_llm.invoke.call_args_list[0][0][0]
    assert "你好" in prompt_arg
