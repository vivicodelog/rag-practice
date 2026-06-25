"""
NL2SQL 模块单元测试。

先测不调 LLM 的辅助函数，再测主逻辑（mock LLM）。
"""

import sqlite3
import pytest

import sys
sys.path.insert(0, "d:/rag-project")

from nl2sql.agent import get_schema, get_column_map


def test_get_column_map_returns_dict():
    """
    get_column_map() 应该返回 {英文列名: 中文列名} 的字典。

    测试策略：
        自己建一个内存里的 SQLite 数据库（:memory:），
        建 column_meta 表，插入几条测试数据，
        然后调 get_column_map(conn) 看结果对不对。

    为什么不用真实数据库？
        - 测试之间互相独立，互不影响
        - 不用每次跑测试前初始化一次数据

    你要做的事：
        1. 用 sqlite3.connect(":memory:") 建一个内存数据库
        2. 建 column_meta 表（CREATE TABLE，字段见 database.py 第 81-88 行）
        3. 插入三条测试数据：
           - author_id → 作者编号
           - name      → 姓名
           - title     → 书名
        4. 调用 get_column_map(conn)
        5. 断言返回结果是 {"author_id": "作者编号", "name": "姓名", "title": "书名"}
        6. 关连接
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE column_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            UNIQUE(table_name, column_name)
        );"""
    )
    cursor.execute(
        """INSERT INTO column_meta (table_name, column_name, display_name) VALUES
        ('books', 'author_id', '作者编号'),
        ('books', 'name', '姓名'),
        ('books', 'title', '书名');
        """
    )
    
    column_map = get_column_map(conn)
    assert column_map == {"author_id": "作者编号", "name": "姓名", "title": "书名"}
    conn.close()

def test_get_schema_returns_string():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (author_id) REFERENCES authors (id)
        );"""
    )
    schema = get_schema(conn)
    # authors(author_id INTEGER PK, name TEXT NOT NULL, ...)
    assert schema == """authors(id INTEGER PK, author_id INTEGER NOT NULL -> authors(id), name TEXT NOT NULL, title TEXT NOT NULL)"""