"""
NL2SQL Agent：自然语言 → SQL → 执行 → 返回结果

流程：
  1. 从 SQLite 读出所有表结构（表名、列名、类型、外键）
  2. 把 schema 拼进 prompt，让 LLM 生成 SQL
  3. 执行 SQL → 返回 {sql, columns, rows}
"""
import sqlite3
import sys, os

# nl2sql/ 内互相引用用 _nl2sql_dir
# 项目根目录（rag_forge/）用 _project_root
_nl2sql_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_nl2sql_dir)
sys.path.insert(0, _project_root)
sys.path.insert(0, _nl2sql_dir)

from database import get_connection, close
from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek
from rag_forge.config import settings


def get_schema() -> str:
    """读取数据库所有表结构，返回格式化文本

    例如：
      authors (author_id INTEGER PK, name TEXT NOT NULL, country TEXT, birth_year INTEGER)
      books (book_id INTEGER PK, author_id INTEGER -> authors.author_id, ...)
    """
    conn = get_connection()
    cursor = conn.cursor()

  
    # 1. 查出所有用户表（排除 sqlite_sequence）
    #    SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
    # 2. 对每个表名，PRAGMA table_info(表名) 拿到列信息
    #    PRAGMA 返回: cid, name, type, notnull, dflt_value, pk
    # cursor.execute("PRAGMA table_info(?)", (table_name,))
    # 3. 如果某列是外键，PRAGMA foreign_key_list(表名) 拿外键信息
    #    PRAGMA 返回: id, seq, table, from, to, on_update, on_delete, match
    # cursor.execute("PRAGMA foreign_key_list(?)", (table_name,))
    # 4. 拼成易读的文本，比如：
      #  books(book_id INTEGER, author_id INTEGER -> authors.author_id, ...)

    # cursor.execute("PRAGMA table_info(?)", (table_name,))
    # 为什么 PRAGMA table_info(?) 会报错？
    # - PRAGMA 本身就不支持 ? 占位符，这是 SQLite 底层的限制
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    table_parts = []
    # for table_name in table_name:   
    for row in cursor.fetchall():
        table_name = row["name"]  
        cursor.execute("PRAGMA table_info("+table_name+")")
        columns = cursor.fetchall()
        cursor.execute("PRAGMA foreign_key_list("+table_name+")")
        # columns 每条是 (cid, name, type, notnull, dflt_value, pk)
        # 需要拼成 "列名 类型 PK/NOT NULL" 的格式
        fk_map = {}
        for fk in cursor.fetchall():
          fk_map[fk[3]] = f"-> {fk[2]}({fk[4]})"
        parts = []
        for col in columns:
            col_name, col_type, notnull, pk = col[1], col[2], col[3], col[5]
            col_str = f"{col_name} {col_type}"
            if pk:   col_str += " PK"
            if notnull: col_str += " NOT NULL"
            if col_name in fk_map: col_str += f" {fk_map[col_name]}"
            parts.append(col_str)
        table_parts.append(f"{table_name}({', '.join(parts)})")
    cursor.close()
    close(conn)
    return "\n".join(table_parts)
def nl2sql(question: str) -> dict:
    """自然语言 → SQL → 执行 → 返回结果"""

    # ── ① 拿表结构 ──
    schema = get_schema()

    # ── ② 拼 prompt ──
    prompt = f"""你是一个 SQLite 专家。根据下面的数据库结构，把用户问题转成 SQL。

数据库结构：
{schema}

要求：
- 只输出 SQL，不要解释、不要多余文字
- 只使用 SELECT 查询
- 列名和表名不要加引号或反引号

用户问题：{question}

SQL："""

    # ── ③ 调 LLM 生成 SQL ──
    llm = ChatDeepSeek(
        api_key=SecretStr(settings.DEEPSEEK_API_KEY),
        model=settings.LLM_MODEL,
        temperature=0.1,
    )
    response = llm.invoke(prompt)
    sql = response.content.strip()

    # 清理 LLM 可能加的 ```sql ... ``` 包裹
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # ── ④ 执行 SQL ──
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]
    cursor.close()
    close(conn)

    return {"sql": sql, "columns": columns, "rows": rows}
if __name__ == "__main__":
    import sys
    question = sys.argv[1] if len(sys.argv) > 1 else "列出所有作者"
    result = nl2sql(question)
    print("SQL:", result["sql"])
    print("列:", result["columns"])
    print("行:", result["rows"])
