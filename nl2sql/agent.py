"""
NL2SQL Agent：自然语言 → SQL → 执行 → 返回结果

流程：
  1. 从 SQLite 读出所有表结构（表名、列名、类型、外键）
  2. 把 schema 拼进 prompt，让 LLM 生成 SQL
  3. 执行 SQL → 返回 {sql, columns, rows}
"""
import re
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


def get_schema(conn=None) -> str:
    """读取数据库所有表结构，返回格式化文本

    例如：
      authors (author_id INTEGER PK, name TEXT NOT NULL, country TEXT, birth_year INTEGER)
      books (book_id INTEGER PK, author_id INTEGER -> authors.author_id, ...)
    """
    #完整比喻：
      # 你有一张 Excel 表，你想把它的结构告诉别人。
      # for col in columns: → 遍历每一列
      # col_name, col_type, ... → 把这列的名字、类型、属性拆出来
      # col_str = f"... → 拼成一段描述（"author_id INTEGER"）
      # if pk: → 如果是主键，加上" PK"
      # parts.append(col_str) → 把每一列的描述收进列表
      # 所有列遍历完，join(parts) → 用逗号粘起来，再套上表名
      # 最后成品：
         # authors(author_id INTEGER PK, name TEXT NOT NULL, ...)       
         
    open_conn = False
    if conn is None: 
        conn = get_connection() 
        open_conn = True
    cursor = conn.cursor()  
    # 1. 查出所有用户表（排除 sqlite_sequence）
    # 2. 对每个表名，PRAGMA table_info(表名) 拿到列信息
    # 3. 如果某列是外键，PRAGMA foreign_key_list(表名) 拿外键信息
    # 4. 拼成易读的文本
    # 为什么 PRAGMA table_info(?) 会报错？
    # - PRAGMA 本身就不支持 ? 占位符，这是 SQLite 底层的限制
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'column_meta'")
    table_parts = []
    # for table_name in table_name:   
    for row in cursor.fetchall():
        table_name = row["name"]  
        if not re.match(r'^\w+$', table_name):
            continue
        cursor.execute("PRAGMA table_info("+table_name+")")
        columns = cursor.fetchall()
        cur_fk = conn.cursor()      
        cur_fk.execute("PRAGMA foreign_key_list("+table_name+")")
        # columns 每条是 (cid, name, type, notnull, dflt_value, pk)
        # 需要拼成 "列名 类型 PK/NOT NULL" 的格式
        fk_map = {fk[3]: f"-> {fk[2]}({fk[4]})" for fk in cur_fk.fetchall()}
        cur_fk.close()
        parts = []
        for col in columns:
            col_name, col_type, notnull, pk = col[1], col[2], col[3], col[5]#col[4]没有默认值，直接省略了，不影响后续
            col_str = f"{col_name} {col_type}"
            if pk:   col_str += " PK"
            if notnull: col_str += " NOT NULL"
            if col_name in fk_map: col_str += f" {fk_map[col_name]}"
            parts.append(col_str)
        table_parts.append(f"{table_name}({', '.join(parts)})")
    cursor.close()
    if open_conn:
        close(conn)
    return "\n".join(table_parts)

def get_column_map(conn = None) -> dict:
    """从 column_meta 表读取字段中文名映射

    查 column_meta 表，拿到所有 (column_name, display_name)
    拼成一个 dict：{"author_id": "作者编号", "name": "姓名", ...}
    供 nl2sql() 转中文列名用
    
    注意：cursor 用完要关，连接也要关
    """
    # 1. get_connection()
    # 2. cursor.execute("SELECT column_name, display_name FROM column_meta")
    # 3. 遍历 cursor.fetchall()，组装成 dict
    #    注意：同一列名可能有多条（不同表），后面的会覆盖前面的，不影响因为中文名是一样的
    # 4. cursor.close() + close(conn)
    # 5. return dict
    open_conn = False
    if conn is None: 
        conn = get_connection() 
        open_conn = True
    cursor = conn.cursor()
    cursor.execute("SELECT column_name, display_name FROM column_meta")
    column_map = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    if open_conn:
        close(conn)
    return column_map



def nl2sql(question: str) -> dict:
    """自然语言 → SQL → 执行 → 返回结果"""

    conn = get_connection()
    cursor = conn.cursor()
    # ── ① 拿表结构 ──
    schema = get_schema(conn)

    # ── ② 拼 prompt ──
    prompt = f"""你是一个 SQLite 专家。根据下面的数据库结构，把用户问题转成 SQL。

数据库结构：
{schema}

要求：
- 只输出 SQL，不要解释、不要多余文字
- 只使用 SELECT 查询
- 列名和表名不要加引号或反引号
- 如果有 AS 别名，用中文且不要加引号（如 COUNT(*) AS 数量）
用户问题：{question}

SQL："""

    # ── ③ 调 LLM 生成 SQL ──
    llm = ChatDeepSeek(
        api_key=SecretStr(settings.DEEPSEEK_API_KEY),
        model=settings.LLM_MODEL,
        temperature=0.1,
    )
    response = llm.invoke(prompt)
    assert isinstance(response.content, str)       # 防御性写法
    sql = response.content.strip()
    columns = []
    rows = []
    error_message = None
    # 清理 LLM 可能加的 ```sql ... ``` 包裹
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # 如果 SQL 没有 LIMIT 子句，追加 LIMIT 100
    if not re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        sql = sql.rstrip() + " LIMIT 100"

    try:
        if sql.strip().upper().startswith("SELECT"):            
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = [list(row) for row in cursor.fetchall()]
        else:
            error_message = "只支持 SELECT 查询"
    except sqlite3.Error as e:
        rows= []
        error_message = str(e)
    # ── ④ 执行 SQL ──
    

    # ── ⑤ 字段名转中文 ──
    #    数据库字段是英文，前端展示需要中文表头
    
    column_map = get_column_map(conn)
    columns = [column_map.get(col, col) for col in columns]

    cursor.close()
    close(conn)

    return {"sql": sql, "columns": columns, "rows": rows,"error": error_message if error_message else None}

if __name__ == "__main__":
    import sys
    question = sys.argv[1] if len(sys.argv) > 1 else "列出所有作者"
    result = nl2sql(question)
    print("SQL:", result["sql"])
    print("列:", result["columns"])
    print("行:", result["rows"])
