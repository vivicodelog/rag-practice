"""
SQLite 会话存储层。
提供会话和消息的 CRUD 操作。
"""

import sqlite3
import uuid
import json
from datetime import datetime, timezone

_db = None
DB_PATH = "data/conversations.db"


def get_db(path=None):
    global _db
    if _db is None:
        _db = sqlite3.connect(path or DB_PATH, check_same_thread=False)
        _db.row_factory = sqlite3.Row   #注释：让查出来的行像字典一样能按列名取值
    return _db

def init_db(db=None):
    conn = db or get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            mode TEXT NOT NULL CHECK(mode IN ('agent', 'workflow', 'nl2sql')),
            title TEXT NOT NULL DEFAULT '新对话',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sql TEXT,
            cols TEXT,
            rows_data TEXT,
            error TEXT

        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_mode ON sessions(mode);

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );       
                       
    """)
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id)")
    except sqlite3.OperationalError:
        pass  # 列已存在

    conn.commit()

def create_session(mode: str, title: str = "新对话",user_id: str|None = None):
    conn = get_db()
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO sessions (id, mode, title, created_at, updated_at,user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, mode, title, now, now, user_id))
    conn.commit()
    row = conn.execute("""
        SELECT s.*, 0 AS message_count
        FROM sessions s
        WHERE s.id = ?
    """, (session_id,)).fetchone()
    return dict(row)

def get_sessions(mode: str,user_id: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        WHERE s.mode = ? AND s.user_id = ?
        GROUP BY s.id
        ORDER BY s.updated_at DESC
    """, (mode,user_id,)).fetchall()
    return [dict(r) for r in rows]   # 空列表也安全


def get_session(session_id: str,user_id: str):
    conn = get_db()
    row = conn.execute("""
        SELECT s.*, COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        WHERE s.id = ? AND s.user_id = ?
        GROUP BY s.id
    """, (session_id,user_id)).fetchone()
    if row is None:
        return None
    return dict(row)

def get_messages(session_id: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT m.*
        FROM messages m
        WHERE m.session_id = ?
        ORDER BY m.created_at ASC
    """, (session_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # 数据库列名 cols/rows_data → 前端期望的 columns/rows
        d["columns"] = json.loads(d.pop("cols")) if d.get("cols") else None
        d["rows"] = json.loads(d.pop("rows_data")) if d.get("rows_data") else None
        result.append(d)
    return result

def save_message(session_id: str, role: str, content: str, sql: str|None = None, cols = None, rows_data = None, error = None):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    # 1. 往 messages 表插一条
    conn.execute("""
        INSERT INTO messages (session_id, role, content, created_at, sql, cols, rows_data, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, role, content, now, sql, json.dumps(cols, ensure_ascii=False) if cols else None, json.dumps(rows_data, ensure_ascii=False) if rows_data else None, error))
    # 2. 更新 sessions 的更新时间
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    conn.commit()


def delete_session(session_id: str,user_id: str):
    conn = get_db()
    conn.execute("""DELETE FROM messages WHERE session_id = ? """, (session_id,))
    conn.execute("""DELETE FROM sessions WHERE id = ? AND user_id = ?""", (session_id,user_id))
    conn.commit()


# ── 用户 CRUD ──────────────────────────────────────────


def create_user(username: str, password_hash: str) -> dict:
    """
    创建用户，返回用户 dict：{id, username, password_hash, created_at}。

    流程：
        - uuid4 生成 id
        - _now() 记 created_at
        - INSERT INTO users
        - commit 后 SELECT * 回读（和 create_session 一样的模式）
        - 返回 dict(row)
    """
    conn = get_db()
    id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO users (id, username, password_hash, created_at)
        VALUES (?, ?, ?, ?)
    """, (id, username, password_hash, now))
    conn.commit()
    row = conn.execute("""
        SELECT * FROM users WHERE id = ?
    """, (id,)).fetchone()
    return dict(row)


def get_user_by_username(username: str) -> dict | None:
    """
    按用户名查用户（登录时用）。
    SELECT * FROM users WHERE username = ? → fetchone
    查到返回 dict，没查到返回 None。
    """
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM users WHERE username = ?
    """, (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    """
    按 id 查用户（/auth/me 时用）。
    同上，WHERE id = ?。
    """
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM users WHERE id = ?
    """, (user_id,)).fetchone()
    return dict(row) if row else None

