# 多会话（Phase 1）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现多会话管理——后端 SQLite 存储 + CRUD API + 前端侧边栏，覆盖 Agent/Workflow/NL2SQL 三种模式。

**架构：** 新增 `backend/database.py` 做 SQLite 存储层，`backend/schemas.py` 加会话模型，`backend/router.py` 加 CRUD 路由并改造现有 chat 端点支持 `session_id`。前端新增 `SessionSidebar.vue` 组件嵌入三个功能标签页。

**技术栈：** Python sqlite3（标准库）、Vue 3 Options API

---

## 文件结构

### 新建
- `backend/database.py` — SQLite 存储层（init_db / CRUD 会话和消息）
- `frontend/src/components/SessionSidebar.vue` — 会话侧边栏组件
- `tests/test_database.py` — database.py 单元测试

### 修改
- `backend/schemas.py` — 加 Session 相关 Pydantic 模型，ChatRequest 加 session_id
- `backend/router.py` — 加会话 CRUD 路由，改造 /chat /chat/workflow /nl2sql 支持 session_id
- `backend/main.py` — 启动时调 init_db()
- `backend/sse.py` — SSE 端点加 session_id 参数
- `frontend/src/api.js` — 加会话 API 方法
- `frontend/view/ChatView.vue` — 嵌入侧边栏 + session_id
- `frontend/view/WorkflowChat.vue` — 嵌入侧边栏 + session_id
- `frontend/src/view/NL2SQLChat.vue` — 嵌入侧边栏 + session_id
- `frontend/src/App.vue` — 调整布局

---

### 任务 1：SQLite 存储层

**文件：**
- 创建：`backend/database.py`
- 创建：`tests/test_database.py`
- 修改：`backend/main.py:30-33`

- [ ] **步骤 1：编写测试**

```python
# tests/test_database.py
"""测试 SQLite 会话存储层"""

import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import get_db, init_db, create_session, get_sessions, \
    get_session, get_messages, save_message, delete_session


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建内存数据库"""
    db = get_db(":memory:")
    init_db(db)
    yield
    db.close()


def test_create_session():
    """创建会话后返回包含 id/mode/title 的 dict"""
    s = create_session("agent", title="测试会话")
    assert s["id"] is not None
    assert s["mode"] == "agent"
    assert s["title"] == "测试会话"
    assert s["created_at"] is not None
    assert s["updated_at"] is not None


def test_create_session_default_title():
    """不传 title 时默认 '新对话'"""
    s = create_session("workflow")
    assert s["title"] == "新对话"


def test_get_sessions_empty():
    """没有会话时返回空列表"""
    assert get_sessions("agent") == []


def test_get_sessions_by_mode():
    """按 mode 过滤"""
    s1 = create_session("agent")
    s2 = create_session("workflow")
    s3 = create_session("agent")
    agent_sessions = get_sessions("agent")
    assert len(agent_sessions) == 2
    assert all(s["mode"] == "agent" for s in agent_sessions)


def test_get_session():
    """按 id 获取会话详情"""
    created = create_session("nl2sql")
    fetched = get_session(created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["mode"] == "nl2sql"


def test_get_session_not_found():
    """不存在的 id 返回 None"""
    assert get_session("non-existent") is None


def test_save_and_get_messages():
    """存消息后能按 session_id 取出"""
    s = create_session("agent")
    save_message(s["id"], "user", "你好")
    save_message(s["id"], "assistant", "你好！")
    msgs = get_messages(s["id"])
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "你好！"


def test_get_messages_empty():
    """新会话没有消息"""
    s = create_session("agent")
    assert get_messages(s["id"]) == []


def test_get_messages_other_session():
    """消息不跨会话混淆"""
    s1 = create_session("agent")
    s2 = create_session("agent")
    save_message(s1["id"], "user", "s1")
    save_message(s2["id"], "user", "s2")
    assert len(get_messages(s1["id"])) == 1
    assert get_messages(s1["id"])[0]["content"] == "s1"


def test_delete_session():
    """删会话同时消息也被删"""
    s = create_session("agent")
    save_message(s["id"], "user", "test")
    delete_session(s["id"])
    assert get_session(s["id"]) is None
    assert get_messages(s["id"]) == []


def test_sessions_ordered_by_updated_at():
    """会话列表按 updated_at 降序（最新在前）"""
    s1 = create_session("agent", title="旧")
    import time
    time.sleep(0.01)
    s2 = create_session("agent", title="新")
    sessions = get_sessions("agent")
    assert sessions[0]["id"] == s2["id"]
    assert sessions[1]["id"] == s1["id"]


def test_session_message_count():
    """get_sessions 返回的每条记录包含 message_count"""
    s = create_session("agent")
    save_message(s["id"], "user", "q")
    save_message(s["id"], "assistant", "a")
    sessions = get_sessions("agent")
    assert sessions[0]["message_count"] == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_database.py -v`
预期：全部 FAIL（ModuleNotFoundError: No module named 'backend.database'）

- [ ] **步骤 3：编写 database.py**

```python
"""
SQLite 会话存储层。

提供会话和消息的 CRUD 操作。
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

# 全局连接，由 init_db 初始化
_db: Optional[sqlite3.Connection] = None

DB_PATH = "data/conversations.db"


def get_db(path: Optional[str] = None) -> sqlite3.Connection:
    """获取数据库连接（单例）。传 path 用于测试时指定 :memory:"""
    global _db
    if _db is None:
        path = path or DB_PATH
        _db = sqlite3.connect(path, check_same_thread=False)
        _db.row_factory = sqlite3.Row
    return _db


def init_db(db: Optional[sqlite3.Connection] = None) -> None:
    """建表"""
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
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_mode ON sessions(mode);
    """)
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(mode: str, title: str = "新对话") -> dict:
    """创建新会话，返回会话 dict"""
    conn = get_db()
    session_id = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO sessions (id, mode, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, mode, title, now, now),
    )
    conn.commit()
    return {"id": session_id, "mode": mode, "title": title, "created_at": now, "updated_at": now}


def get_sessions(mode: str) -> list[dict]:
    """按 mode 列出会话（含消息数），按 updated_at 降序"""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT s.id, s.mode, s.title, s.created_at, s.updated_at,
               COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        WHERE s.mode = ?
        GROUP BY s.id
        ORDER BY s.updated_at DESC
        """,
        (mode,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_session(session_id: str) -> Optional[dict]:
    """获取单个会话"""
    conn = get_db()
    row = conn.execute(
        "SELECT id, mode, title, created_at, updated_at FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None


def get_messages(session_id: str) -> list[dict]:
    """获取会话的所有消息，按创建时间升序"""
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_message(session_id: str, role: str, content: str) -> None:
    """保存一条消息并更新会话的 updated_at"""
    conn = get_db()
    now = _now()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    conn.commit()


def delete_session(session_id: str) -> None:
    """删除会话（外键 CASCADE 自动删消息）"""
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
```

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_database.py -v`
预期：全部 PASS

- [ ] **步骤 5：在 main.py startup 中初始化数据库**

```python
# backend/main.py 第 30-33 行附近，import 区域加一行
from backend.database import init_db

# lifespan 函数第一行加
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载模型和构建向量库"""
    logger.info("正在初始化 RAG 系统...")
    init_db()  # ← 建会话表
    # ... 下面的代码不动 ...
```

- [ ] **步骤 6：Commit**

```bash
git add backend/database.py tests/test_database.py backend/main.py
git commit -m "feat: SQLite 会话存储层（database.py + 测试）"
```

---

### 任务 2：会话 Pydantic 模型

**文件：**
- 修改：`backend/schemas.py`

- [ ] **步骤 1：添加会话相关模型**

```python
# 在 backend/schemas.py 末尾，NL2SQLResponse 之后添加

# ── 会话管理 ──────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    mode: str  # "agent" | "workflow" | "nl2sql"
    title: Optional[str] = "新对话"


class SessionItem(BaseModel):
    """会话摘要"""
    id: str
    mode: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class SessionDetail(BaseModel):
    """会话详情（含消息）"""
    id: str
    mode: str
    title: str
    created_at: str
    updated_at: str
    messages: list
```

- [ ] **步骤 2：修改 ChatRequest 加 session_id**

```python
class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    history: Optional[List[dict]] = []
    session_id: Optional[str] = None  # ← 新增
```

- [ ] **步骤 3：Commit**

```bash
git add backend/schemas.py
git commit -m "feat: 添加会话 Pydantic 模型 + ChatRequest 加 session_id"
```

---

### 任务 3：会话 CRUD 路由

**文件：**
- 修改：`backend/router.py`

- [ ] **步骤 1：编写测试**

```python
# tests/test_sessions_api.py
"""测试会话 CRUD API"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db, init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """每个测试重置为内存数据库"""
    db = get_db(":memory:")
    init_db(db)
    yield
    db.close()


def test_create_session():
    """POST /sessions 返回新建的会话"""
    resp = client.post("/sessions", json={"mode": "agent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "agent"
    assert data["title"] == "新对话"
    assert data["id"] is not None


def test_create_session_invalid_mode():
    """无效 mode 返回 400"""
    resp = client.post("/sessions", json={"mode": "invalid"})
    assert resp.status_code == 400


def test_list_sessions():
    """GET /sessions?mode=agent 返回过滤后的列表"""
    client.post("/sessions", json={"mode": "agent"})
    client.post("/sessions", json={"mode": "workflow"})
    client.post("/sessions", json={"mode": "agent"})
    resp = client.get("/sessions?mode=agent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sessions"]) == 2


def test_get_session():
    """GET /sessions/{id} 返回会话详情"""
    created = client.post("/sessions", json={"mode": "agent"}).json()
    resp = client.get(f"/sessions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_session_not_found():
    """不存在的 id 返回 404"""
    resp = client.get("/sessions/not-exist")
    assert resp.status_code == 404


def test_delete_session():
    """DELETE /sessions/{id} 删除成功"""
    created = client.post("/sessions", json={"mode": "agent"}).json()
    resp = client.delete(f"/sessions/{created['id']}")
    assert resp.status_code == 200
    # 删后再查返回 404
    resp = client.get(f"/sessions/{created['id']}")
    assert resp.status_code == 404
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_sessions_api.py -v`
预期：全部 FAIL（404，路由未注册）

- [ ] **步骤 3：在 router.py 添加会话 CRUD 路由**

```python
# 在 backend/router.py 顶部 import 区域加
from backend.schemas import (
    ChatRequest, ChatResponse, SourceItem, UploadResponse,
    WorkflowResponse, NL2SQLRequest, NL2SQLResponse,
    SessionCreateRequest, SessionItem, SessionDetail,  # ← 新增
)
from backend.database import (
    create_session, get_sessions, get_session,
    get_messages, save_message, delete_session,
)

# 在文件末尾添加
# ── 会话管理 ──────────────────────────────────────────

@router.post("/sessions")
def api_create_session(req: SessionCreateRequest):
    """创建会话"""
    valid_modes = ("agent", "workflow", "nl2sql")
    if req.mode not in valid_modes:
        raise HTTPException(400, f"无效 mode，可选值：{valid_modes}")
    session = create_session(req.mode, req.title)
    return session


@router.get("/sessions")
def api_list_sessions(mode: str = "agent"):
    """列出会话"""
    sessions = get_sessions(mode)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
def api_get_session(session_id: str):
    """获取会话详情（含消息）"""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    messages = get_messages(session_id)
    return {**session, "messages": messages}


@router.delete("/sessions/{session_id}")
def api_delete_session(session_id: str):
    """删除会话"""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    delete_session(session_id)
    return {"success": True}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_sessions_api.py -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/router.py backend/schemas.py tests/test_sessions_api.py
git commit -m "feat: 会话 CRUD API（建/列/查/删）"
```

---

### 任务 4：改造现有 chat 端点支持 session_id

**文件：**
- 修改：`backend/router.py`

**改动说明**：三个 chat 端点（/chat、/chat/workflow、/nl2sql）收到 session_id 后，存历史消息到 SQLite。不改造 SSE 端点（下个任务单独处理）。

- [ ] **步骤 1：编写测试**

在 `tests/test_sessions_api.py` 末尾追加：

```python
def test_chat_saves_messages():
    """带 session_id 的聊天会自动保存消息"""
    # 创建会话
    s = client.post("/sessions", json={"mode": "agent"}).json()
    sid = s["id"]
    # 发消息
    resp = client.post("/chat", json={
        "question": "你好",
        "session_id": sid,
    })
    assert resp.status_code == 200
    # 验证消息被保存
    detail = client.get(f"/sessions/{sid}").json()
    # 至少有一条 user 消息
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles


def test_chat_without_session_id():
    """不带 session_id 的聊天不受影响"""
    resp = client.post("/chat", json={"question": "测试"})
    assert resp.status_code in (200, 503)  # 503 是因为 vectordb 未初始化


def test_chat_session_preserves_history():
    """同一 session 的多轮消息都存进去"""
    s = client.post("/sessions", json={"mode": "agent"}).json()
    sid = s["id"]
    client.post("/chat", json={"question": "第一轮", "session_id": sid})
    client.post("/chat", json={"question": "第二轮", "session_id": sid})
    detail = client.get(f"/sessions/{sid}").json()
    user_msgs = [m for m in detail["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 2
```

- [ ] **步骤 2：修改 /chat 端点**

在 `/chat` 路由函数体中，`return ChatResponse(...)` 之前插入：

```python
# 保存消息到会话
if request.session_id:
    save_message(request.session_id, "user", request.question)
    if answer:
        save_message(request.session_id, "assistant", answer)
```

位置：第 103 行 `return ChatResponse(answer=answer, sources=sources)` 之前。

完整的修改后 /chat 函数：

```python
@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """问答接口：Agent 模式，LLM 自主选择工具"""
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    try:
        llm_with_tools = state.llm.bind_tools([get_weather, search_docs, query_database])
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        # 如果带了 session_id，从数据库读历史
        history = request.history or []
        if request.session_id:
            db_msgs = get_messages(request.session_id)
            if db_msgs:
                history = [{"role": m["role"], "content": m["content"]} for m in db_msgs]

        trimmed = trim_history(history, state.llm, settings.MAX_HISTORY_ROUNDS)
        for msg in trimmed:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                messages.append(SystemMessage(content=msg["content"]))

        messages.append(HumanMessage(content=request.question))
        sources = []

        for _ in range(3):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"].lower()
                tool_args = tool_call["args"]

                if tool_name == "search_docs":
                    result = search_docs.invoke(tool_args)
                    if result not in ("未找到相关文档", "知识库尚未初始化，请先上传文档"):
                        raw = hybrid_search(
                            query=tool_args["query"],
                            vectordb=state.vectordb,
                            all_chunks=state.all_chunks,
                            top_k=6,
                            reranker=state.reranker,
                        )
                        sources = [
                            SourceItem(
                                filename=os.path.basename(s) if s else "未知",
                                score=score,
                                content=c[:200],
                            )
                            for c, score, s in raw
                        ]
                elif tool_name == "get_weather":
                    result = get_weather.invoke(tool_args)
                elif tool_name == "query_database":
                    result = query_database.invoke(tool_args)
                else:
                    result = f"未知工具：{tool_name}"

                messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

        answer = messages[-1].content if isinstance(messages[-1].content, str) else ""

        # 保存消息到会话
        if request.session_id:
            save_message(request.session_id, "user", request.question)
            if answer:
                save_message(request.session_id, "assistant", answer)

        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"聊天接口异常：{e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **步骤 3：修改 /chat/workflow 端点**

在 `/chat/workflow` 函数中，保存历史消息：

```python
@router.post("/chat/workflow", response_model=WorkflowResponse)
def chat_workflow(request: ChatRequest):
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    researcher_prompt = state.researcher_prompt
    writer_prompt = state.writer_prompt
    reviewer_prompt = state.reviewer_prompt

    researcher_node = WorkflowNode(
        role="researcher",
        tools=[search_docs],
        prompt=researcher_prompt,
        output_key="research",
        output_type="text",
    )
    writer_node = WorkflowNode(
        role="writer",
        tools=[],
        prompt=writer_prompt,
        output_key="answer",
    )
    reviewer_node = WorkflowNode(
        role="reviewer",
        tools=[review_result],
        prompt=reviewer_prompt,
        output_key="review",
        output_type="tool",
    )
    nodes = [researcher_node, writer_node, reviewer_node]

    # 如果带了 session_id，从数据库读历史
    history = request.history or []
    if request.session_id:
        db_msgs = get_messages(request.session_id)
        if db_msgs:
            history = [{"role": m["role"], "content": m["content"]} for m in db_msgs]

    trimmed = trim_history(history, state.llm, settings.MAX_HISTORY_ROUNDS)
    workflow = Workflow(nodes=nodes, llm=state.llm, history=trimmed)
    result = workflow.run(request.question)

    # 保存消息到会话
    if request.session_id:
        save_message(request.session_id, "user", request.question)
        save_message(request.session_id, "assistant", result["answer"])

    return WorkflowResponse(answer=result["answer"], steps=result["steps"])
```

- [ ] **步骤 4：修改 /nl2sql 端点**

```python
@router.post("/nl2sql", response_model=NL2SQLResponse)
def nl2sql_chat(request: NL2SQLRequest):
    history = request.history or []
    if request.session_id:
        db_msgs = get_messages(request.session_id)
        if db_msgs:
            history = [{"role": m["role"], "content": m["content"]} for m in db_msgs]

    result = nl2sql(request.question, history)

    # 保存消息到会话
    if request.session_id:
        save_message(request.session_id, "user", request.question)
        assistant_content = f"SQL: {result['sql']}\n结果: {len(result['rows'])} 条记录"
        save_message(request.session_id, "assistant", assistant_content)

    return NL2SQLResponse(**result)
```

注意：`NL2SQLRequest` 也要加 `session_id` 字段。

```python
class NL2SQLRequest(BaseModel):
    """NL2SQL 查询请求"""
    question: str
    history: Optional[List[dict]] = []
    session_id: Optional[str] = None  # ← 新增
```

- [ ] **步骤 5：运行测试验证通过**

运行：`pytest tests/test_sessions_api.py::test_chat_saves_messages tests/test_sessions_api.py::test_chat_without_session_id tests/test_sessions_api.py::test_chat_session_preserves_history -v`

- [ ] **步骤 6：Commit**

```bash
git add backend/router.py backend/schemas.py
git commit -m "feat: chat 端点支持 session_id 自动保存消息"
```

---

### 任务 5：SSE 端点支持 session_id

**文件：**
- 修改：`backend/sse.py`

- [ ] **步骤 1：给 SSE 端点加 session_id 参数**

`stream_agent` 和 `stream_workflow` 的 `Query` 参数都加 `session_id`：

```python
@router.get("/chat/agent/stream")
def stream_agent(
    question: str = Query(...),
    history: str = Query("[]"),
    session_id: str = Query(None),  # ← 新增
):
```

```python
@router.get("/chat/workflow/stream")
def stream_workflow(
    question: str = Query(...),
    history: str = Query("[]"),
    session_id: str = Query(None),  # ← 新增
):
```

- [ ] **步骤 2：stream_agent 中保存消息**

在 `stream_agent` 的 `event_stream()` 里，`yield _sse("done", ...)` 之前保存：

```python
# 在 final_answer 赋值后，yield done 之前加入
if session_id:
    save_message(session_id, "user", question)
    save_message(session_id, "assistant", final_answer)
```

位置：第 197-200 行 `break` → `yield _sse("done", ...)` 之间。

注意：import 顶部加 `from backend.database import save_message`

- [ ] **步骤 3：stream_workflow 中保存消息**

在 `stream_workflow` 的 `event_stream()` 里，`yield _sse("done", ...)` 之前保存。

但 workflow stream 并不直接知道最终 answer——它在 node_start/node_end 等事件中流转。最稳妥的方法是：在 yield done 之前，用一个变量记录最后生成的 answer。

在 `event_stream` 函数开始处加 `final_answer = ""`，在工作流的循环中当 event 是 `"node_end"` 且 role 是 writer 时，记录 output 为 final_answer。最后 yield done 前保存。

简化方案：只保存 user 消息，assistant 消息在 SSE 全流程结束后由前端或者靠 done 事件中的数据保存。

更简单的做法——在 yield done 前，把 user 和 assistant 都保存：

```python
try:
    final_answer = ""
    for event in workflow.stream(question):
        if event["event"] == "node_end" and event["data"].get("role") == "writer":
            final_answer = event["data"].get("output", "")
        yield _sse(event["event"], event["data"])
    
    if session_id:
        save_message(session_id, "user", question)
        if final_answer:
            save_message(session_id, "assistant", final_answer)
except Exception as e:
    yield _sse("error", {"message": str(e)})
```

- [ ] **步骤 4：Commit**

```bash
git add backend/sse.py
git commit -m "feat: SSE 端点支持 session_id 自动保存消息"
```

---

### 任务 6：前端 API 层 — 加会话请求方法

**文件：**
- 修改：`frontend/src/api.js`

- [ ] **步骤 1：添加会话 API 方法**

```javascript
// 在 frontend/src/api.js 末尾追加

/** 会话管理 ───────────────────────────────────── */

/** 创建会话 */
export async function createSession(mode, title = '新对话') {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, title }),
  })
  return res.json()
}

/** 获取会话列表 */
export async function getSessions(mode) {
  const res = await fetch(`${BASE}/sessions?mode=${mode}`)
  return res.json()
}

/** 获取会话详情（含消息） */
export async function getSessionDetail(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`)
  return res.json()
}

/** 删除会话 */
export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  return res.json()
}

/** 带 session_id 的聊天（非流式） */
export async function chatWithSession(question, sessionId, history = []) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history, session_id: sessionId }),
  })
  return res.json()
}

/** 带 session_id 的 NL2SQL */
export async function nl2sqlWithSession(question, sessionId, history = []) {
  const res = await fetch(`${BASE}/nl2sql`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history, session_id: sessionId }),
  })
  return res.json()
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: 前端 API 加会话相关方法"
```

---

### 任务 7：前端 SessionSidebar 组件

**文件：**
- 创建：`frontend/src/components/SessionSidebar.vue`

- [ ] **步骤 1：编写组件**

```vue
<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <h3 class="sidebar-title">会话</h3>
      <button class="btn-new" @click="handleNew" title="新建会话">＋</button>
    </div>
    <div class="session-list">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeId }"
        @click="$emit('select', s.id)"
      >
        <div class="session-title">{{ s.title }}</div>
        <div class="session-meta">{{ s.message_count }} 条消息</div>
        <button class="btn-del" @click.stop="handleDelete(s.id)" title="删除">×</button>
      </div>
      <div v-if="!sessions.length" class="empty">暂无会话</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  activeId: { type: String, default: null },
})

const emit = defineEmits(['select', 'new', 'delete'])

function handleNew() {
  emit('new')
}

function handleDelete(id) {
  if (confirm('确定删除此会话？')) {
    emit('delete', id)
  }
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  min-width: 240px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin: 0;
}
.btn-new {
  width: 28px;
  height: 28px;
  border: 1px dashed #ccc;
  border-radius: 6px;
  background: transparent;
  color: #666;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.btn-new:hover {
  border-color: #4a90d9;
  color: #4a90d9;
  background: #f0f5ff;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.session-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 4px;
}
.session-item:hover {
  background: #f5f5f5;
}
.session-item.active {
  background: #f0f5ff;
}
.session-title {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 20px;
}
.session-meta {
  font-size: 11px;
  color: #999;
}
.btn-del {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  color: #ccc;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  display: none;
  align-items: center;
  justify-content: center;
}
.session-item:hover .btn-del {
  display: flex;
}
.btn-del:hover {
  color: #d32f2f;
  background: #fbe9e7;
}
.empty {
  text-align: center;
  color: #bbb;
  padding: 24px 0;
  font-size: 13px;
}
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/SessionSidebar.vue
git commit -m "feat: SessionSidebar 会话侧边栏组件"
```

---

### 任务 8：前端 ChatView 接入会话

**文件：**
- 修改：`frontend/view/ChatView.vue`

改动要点：
1. 引入 `SessionSidebar` 组件
2. 引入会话 API 方法
3. onMounted 时加载会话列表
4. 选择会话后加载历史消息
5. 新建会话时自动创建并选中
6. 删除会话后自动切换到下一个
7. SSE 连接时带上 session_id

- [ ] **步骤 1：修改 ChatView.vue**

```vue
<template>
  <div class="chat-layout">
    <SessionSidebar
      :sessions="sessions"
      :activeId="activeSessionId"
      @select="selectSession"
      @new="createNewSession"
      @delete="deleteSession"
    />
    <div class="chat-container">
      <!-- 消息列表（保持原样） -->
      <div class="messages" ref="msgBox">
        <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
          <div class="bubble">
            <div class="content">{{ msg.content }}</div>
            <div v-if="msg.sources && msg.sources.length" class="sources">
              <span v-for="s in msg.sources" :key="s.filename" class="source-tag">
                📄 {{ s.filename }} {{ (s.score * 100).toFixed(0) }}%
              </span>
            </div>
          </div>
        </div>
        <div v-if="loading" class="message-row assistant">
          <div class="bubble loading-bubble">
            <span class="dot-pulse">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
          </div>
        </div>
      </div>
      <!-- 输入区（保持原样） -->
      <div class="input-area">
        <input v-model="question" @keyup.enter="send" placeholder="输入问题..." />
        <button @click="send" :disabled="loading || !question.trim()">{{ loading ? '思考中' : '发送' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted } from 'vue'
import { chat, getSessions, getSessionDetail, createSession, deleteSession as delSession } from '../src/api.js'
import SessionSidebar from '../src/components/SessionSidebar.vue'

const question = ref('')
const messages = ref([])
const loading = ref(false)
const msgBox = ref(null)

// 会话管理
const sessions = ref([])
const activeSessionId = ref(null)

// 加载会话列表
async function loadSessions() {
  const res = await getSessions('agent')
  sessions.value = res.sessions || []
}

// 选择会话
async function selectSession(id) {
  activeSessionId.value = id
  const detail = await getSessionDetail(id)
  messages.value = (detail.messages || []).map(m => ({
    role: m.role,
    content: m.content,
    sources: [],
  }))
}

// 新建会话
async function createNewSession() {
  const s = await createSession('agent')
  sessions.value.unshift(s)
  activeSessionId.value = s.id
  messages.value = []
}

// 删除会话
async function deleteSession(id) {
  await delSession(id)
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (activeSessionId.value === id) {
    activeSessionId.value = sessions.value[0]?.id || null
    if (activeSessionId.value) {
      selectSession(activeSessionId.value)
    } else {
      messages.value = []
    }
  }
}

// 初始化
onMounted(async () => {
  await loadSessions()
  if (sessions.value.length) {
    activeSessionId.value = sessions.value[0].id
    await selectSession(activeSessionId.value)
  }
})

// 滚动（保持原样）
watch([messages, loading], async () => {
  await nextTick()
  if (msgBox.value) {
    msgBox.value.scrollTop = msgBox.value.scrollHeight
  }
}, { deep: true })

// send 函数改造
async function send() {
  if (!question.value.trim()) return

  // 没选中会话时自动建一个
  if (!activeSessionId.value) {
    await createNewSession()
  }

  const q = question.value
  messages.value.push({ role: 'user', content: q })
  messages.value.push({ role: 'assistant', content: '', sources: [] })
  question.value = ''
  loading.value = true

  // SSE 连接带上 session_id
  const history = JSON.stringify(
    messages.value.slice(0, -2).map(m => ({
      role: m.role,
      content: m.content || ''
    }))
  )

  const url = `http://localhost:8000/chat/agent/stream?question=${encodeURIComponent(q)}&history=${encodeURIComponent(history)}&session_id=${activeSessionId.value}`
  const es = new EventSource(url)
  let doneReceived = false

  es.addEventListener('token', (e) => {
    const data = JSON.parse(e.data)
    const lastMsg = messages.value[messages.value.length - 1]
    lastMsg.content += data.text
  })

  es.addEventListener('done', (e) => {
    const data = JSON.parse(e.data)
    const lastMsg = messages.value[messages.value.length - 1]
    lastMsg.content = data.answer
    lastMsg.sources = data.sources
    doneReceived = true
    es.close()
    loading.value = false
    // 刷新会话列表（消息数变了）
    loadSessions()
  })

  es.addEventListener('error', () => {
    if (doneReceived) return
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg) lastMsg.error = '连接中断，请重试'
    loading.value = false
    es.close()
  })
}
</script>

<style scoped>
/* 新增外层布局 */
.chat-layout {
  display: flex;
  height: 80vh;
  max-width: 1100px;
  margin: 0 auto;
  background: #f5f5f5;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}
/* 以下保持原 ChatView 的样式，不需要改 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 15px;
  line-height: 1.6;
  word-wrap: break-word;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.user .bubble {
  background: #4a90d9;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.assistant .bubble {
  background: #fff;
  color: #333;
  border-bottom-left-radius: 4px;
  border: 1px solid #e5e5e5;
}
.sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid rgba(0,0,0,0.06);
}
.source-tag {
  font-size: 11px;
  background: rgba(255,255,255,0.7);
  color: #555;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.loading-bubble {
  background: #fff !important;
  border: 1px solid #e5e5e5;
}
.dot-pulse { color: #999; font-size: 14px; }
.dot { animation: blink 1.4s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
.dot:nth-child(4) { animation-delay: 0.6s; }
@keyframes blink { 0%,100% { opacity: 0.3; } 50% { opacity: 1; } }
.input-area {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e0e0e0;
}
.input-area input {
  flex: 1;
  padding: 12px 16px;
  font-size: 15px;
  border: 1px solid #d0d0d0;
  border-radius: 24px;
  outline: none;
  transition: border 0.2s;
}
.input-area input:focus { border-color: #4a90d9; }
.input-area button {
  padding: 12px 24px;
  font-size: 15px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 24px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}
.input-area button:hover:not(:disabled) { background: #357abd; }
.input-area button:disabled { background: #b0c4de; cursor: not-allowed; }
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/view/ChatView.vue
git commit -m "feat: ChatView 接入会话侧边栏"
```

---

### 任务 9：前端 WorkflowChat 接入会话

**文件：**
- 修改：`frontend/view/WorkflowChat.vue`

改动与 ChatView 类似：
1. 加 SessionSidebar
2. onMounted 加载 workflow 会话列表
3. send 时带 session_id
4. 新建/切换/删除会话

- [ ] **步骤 1：修改 WorkflowChat.vue**

```vue
<template>
  <div class="workflow-layout">
    <SessionSidebar
      :sessions="sessions"
      :activeId="activeSessionId"
      @select="selectSession"
      @new="createNewSession"
      @delete="deleteSession"
    />
    <div class="workflow-chat">
      <!-- 消息列表（保持原样） -->
      <div class="messages" ref="msgBox">
        <!-- ... 完全保持原 WorkflowChat.vue 的模板内容不变 ... -->
        <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
          <div v-if="msg.role === 'user'" class="bubble user-bubble">
            {{ msg.content }}
          </div>
          <div v-else class="bubble assistant-bubble">
            <div v-if="msg.steps && msg.steps.length" class="steps">
              <div v-for="s in msg.steps" :key="s.role" class="step-row">
                <span class="step-icon" :class="s.status">
                  <template v-if="s.status === 'pending'">○</template>
                  <template v-else-if="s.status === 'running'">◌</template>
                  <template v-else-if="s.status === 'done'">✓</template>
                </span>
                <span class="step-role">{{ { researcher: '🔍 研究员', writer: '✍️ 写作者', reviewer: '✅ 审查员' }[s.role] || s.role }}</span>
                <span v-if="s.role === 'reviewer' && s.passed !== null" class="step-verdict" :class="{ pass: s.passed, fail: !s.passed }">
                  {{ s.passed ? '通过' : `未通过（已重写 ${s.rewriteCount} 次）` }}
                </span>
                <div v-if="s.role === 'reviewer' && s.passed === false && s.issues.length" class="step-issues">
                  <div v-for="(issue, j) in s.issues" :key="j" class="issue-item">• {{ issue }}</div>
                </div>
                <div v-if="s.actions && s.actions.length" class="step-actions">
                  <div v-for="(action, j) in s.actions" :key="j" class="action-item">{{ action }}</div>
                </div>
              </div>
            </div>
            <div v-if="msg.content" class="divider"></div>
            <div v-if="msg.content" class="answer">{{ msg.content }}</div>
            <div v-if="msg.sources && msg.sources.length" class="sources">
              <span v-for="s in msg.sources" :key="s.filename" class="source-tag">📄 {{ s.filename }} {{ (s.score * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="msg.error" class="error-msg">{{ msg.error }}</div>
          </div>
        </div>
        <div v-if="loading" class="message-row assistant">
          <div class="bubble loading-bubble">
            <span class="dot-pulse">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
          </div>
        </div>
      </div>
      <div class="input-area">
        <input v-model="question" @keyup.enter="send" placeholder="输入问题..." :disabled="loading" />
        <button @click="send" :disabled="loading || !question.trim()">{{ loading ? '思考中' : '发送' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted } from 'vue'
import { getSessions, getSessionDetail, createSession, deleteSession as delSession } from '../src/api.js'
import SessionSidebar from '../src/components/SessionSidebar.vue'

const messages = ref([])
const question = ref('')
const loading = ref(false)
const msgBox = ref(null)

// 会话管理
const sessions = ref([])
const activeSessionId = ref(null)

async function loadSessions() {
  const res = await getSessions('workflow')
  sessions.value = res.sessions || []
}

async function selectSession(id) {
  activeSessionId.value = id
  const detail = await getSessionDetail(id)
  messages.value = (detail.messages || []).map(m => ({
    role: m.role,
    content: m.content,
    steps: [],
    sources: [],
    error: '',
  }))
}

async function createNewSession() {
  const s = await createSession('workflow')
  sessions.value.unshift(s)
  activeSessionId.value = s.id
  messages.value = []
}

async function deleteSession(id) {
  await delSession(id)
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (activeSessionId.value === id) {
    activeSessionId.value = sessions.value[0]?.id || null
    if (activeSessionId.value) selectSession(activeSessionId.value)
    else messages.value = []
  }
}

onMounted(async () => {
  await loadSessions()
  if (sessions.value.length) {
    activeSessionId.value = sessions.value[0].id
    await selectSession(activeSessionId.value)
  }
})

watch([messages, loading], async () => {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}, { deep: true })

function send() {
  if (!question.value.trim()) return
  if (!activeSessionId.value) { createNewSession(); return }

  const q = question.value
  messages.value.push({ role: 'user', content: q })
  messages.value.push({
    role: 'assistant',
    content: '',
    steps: [
      { role: 'researcher', status: 'pending', actions: [], output: '' },
      { role: 'writer', status: 'pending', actions: [], output: '' },
      { role: 'reviewer', status: 'pending', passed: null, issues: [], rewriteCount: 0 },
    ],
    sources: [],
    error: '',
  })
  question.value = ''
  loading.value = true

  const history = JSON.stringify(
    messages.value.slice(0, -2).map(m => ({ role: m.role, content: m.content || '' }))
  )
  const url = `http://localhost:8000/chat/workflow/stream?question=${encodeURIComponent(q)}&history=${encodeURIComponent(history)}&session_id=${activeSessionId.value}`
  const es = new EventSource(url)
  let doneReceived = false

  es.addEventListener('node_start', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === data.role)
    if (step) step.status = 'running'
  })
  es.addEventListener('node_action', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === data.role)
    if (step) step.actions.push(data.action)
  })
  es.addEventListener('node_end', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === data.role)
    if (!step) return
    step.status = 'done'
    if (data.rewrite && data.role === 'writer') step.status = 'pending'
    step.output = data.output
  })
  es.addEventListener('review_result', (e) => {
    const data = JSON.parse(e.data)
    const step = messages.value[messages.value.length - 1].steps.find(s => s.role === 'reviewer')
    if (!step) return
    step.passed = data.passed
    step.issues = data.issues || []
    step.rewriteCount = data.rewrite_count || 0
    step.status = data.passed ? 'done' : 'running'
  })
  es.addEventListener('done', (e) => {
    try {
      const data = JSON.parse(e.data)
      const lastMsg = messages.value[messages.value.length - 1]
      lastMsg.content = data.answer
    } catch (err) { console.error('done event error:', err) }
    doneReceived = true
    es.close()
    loading.value = false
    loadSessions()
  })
  es.addEventListener('error', () => {
    if (doneReceived) return
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg) lastMsg.error = '连接中断，请重试'
    loading.value = false
    es.close()
  })
}
</script>

<style scoped>
.workflow-layout {
  display: flex;
  height: 80vh;
  max-width: 1100px;
  margin: 0 auto;
  background: #f5f5f5;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.workflow-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
}
/* 以下完全保持原 WorkflowChat.vue 的样式不变 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.6; word-wrap: break-word; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.user-bubble { background: #4a90d9; color: #fff; border-bottom-right-radius: 4px; }
.assistant-bubble { background: #fff; color: #333; border-bottom-left-radius: 4px; border: 1px solid #e5e5e5; }
.steps { margin-bottom: 4px; }
.step-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 4px 0; font-size: 14px; }
.step-icon { width: 18px; text-align: center; font-size: 16px; }
.step-icon.running { color: #e67e22; }
.step-icon.done { color: #27ae60; }
.step-role { font-weight: 500; }
.step-verdict { font-size: 12px; padding: 1px 8px; border-radius: 10px; }
.step-verdict.pass { background: #e8f5e9; color: #27ae60; }
.step-verdict.fail { background: #fbe9e7; color: #d32f2f; }
.step-issues { width: 100%; margin: 2px 0 0 24px; font-size: 12px; color: #d32f2f; }
.issue-item { line-height: 1.5; }
.step-actions { width: 100%; margin: 2px 0 0 24px; font-size: 12px; color: #888; }
.action-item { line-height: 1.5; }
.divider { height: 1px; background: #e8e8e8; margin: 8px 0; }
.answer { font-size: 15px; line-height: 1.7; }
.sources { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; padding-top: 6px; border-top: 1px solid #eee; }
.source-tag { font-size: 11px; background: #f0f5ff; color: #555; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.error-msg { margin-top: 8px; font-size: 13px; color: #d32f2f; padding: 6px 10px; background: #fbe9e7; border-radius: 8px; }
.loading-bubble { background: #fff !important; border: 1px solid #e5e5e5; }
.dot-pulse { color: #999; font-size: 14px; }
.dot { animation: blink 1.4s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
.dot:nth-child(4) { animation-delay: 0.6s; }
@keyframes blink { 0%,100% { opacity: 0.3; } 50% { opacity: 1; } }
.input-area { display: flex; gap: 10px; padding: 16px 20px; background: #fff; border-top: 1px solid #e0e0e0; }
.input-area input { flex: 1; padding: 12px 16px; font-size: 15px; border: 1px solid #d0d0d0; border-radius: 24px; outline: none; transition: border 0.2s; }
.input-area input:focus { border-color: #4a90d9; }
.input-area button { padding: 12px 24px; font-size: 15px; background: #4a90d9; color: #fff; border: none; border-radius: 24px; cursor: pointer; transition: background 0.2s; white-space: nowrap; }
.input-area button:hover:not(:disabled) { background: #357abd; }
.input-area button:disabled { background: #b0c4de; cursor: not-allowed; }
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/view/WorkflowChat.vue
git commit -m "feat: WorkflowChat 接入会话侧边栏"
```

---

### 任务 10：前端 NL2SQLChat 接入会话

**文件：**
- 修改：`frontend/src/view/NL2SQLChat.vue`

改动与上面类似：加侧边栏 + session_id。

注意：NL2SQLChat.vue 在 `frontend/src/view/` 下（不是 `frontend/view/`），且不走 SSE，用的是普通 POST。

- [ ] **步骤 1：修改 NL2SQLChat.vue**

改动要点：
1. 模板包裹 `<div class="nl2sql-layout">` + SessionSidebar
2. script 加会话管理
3. send 带 session_id

```vue
<template>
  <div class="nl2sql-layout">
    <SessionSidebar
      :sessions="sessions"
      :activeId="activeSessionId"
      @select="selectSession"
      @new="createNewSession"
      @delete="deleteSession"
    />
    <div class="nl2sql-chat">
      <!-- 消息列表（基本保持原样） -->
      <div class="messages" ref="msgBox">
        <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
          <div class="bubble">
            <div class="content">{{ msg.content }}</div>
            <div v-if="msg.sql" class="sources">
              📄 <pre>{{ msg.sql }}</pre>
            </div>
            <VChart v-if="getChartOption(msg)" :option="getChartOption(msg)" autoresize class="chart" />
            <div v-if="msg.columns && msg.rows" class="table">
              <table class="table-auto w-full">
                <thead>
                  <tr>
                    <th v-for="(col, j) in msg.columns" :key="j">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in msg.rows" :key="i">
                    <td v-for="(col, j) in row" :key="j">{{ col ? col : '暂无数据' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div v-if="loading" class="message-row assistant">
          <div class="bubble loading-bubble">
            <span class="dot-pulse">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
          </div>
        </div>
      </div>
      <div class="input-area">
        <input v-model="question" @keyup.enter="send" placeholder="输入问题..." />
        <button @click="send" :disabled="loading || !question.trim()">{{ loading ? '思考中' : '发送' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSessions, getSessionDetail, createSession, deleteSession as delSession } from '../api.js'
import { nl2sql } from '../api.js'  // 还是用 nl2sql 函数，后端会在 NL2SQLRequest 里读 session_id
import VChart from 'vue-echarts'
import 'echarts'
import SessionSidebar from '../components/SessionSidebar.vue'

const messages = ref([])
const question = ref('')
const loading = ref(false)
const msgBox = ref(null)

// 会话管理
const sessions = ref([])
const activeSessionId = ref(null)

async function loadSessions() {
  const res = await getSessions('nl2sql')
  sessions.value = res.sessions || []
}

async function selectSession(id) {
  activeSessionId.value = id
  const detail = await getSessionDetail(id)
  messages.value = (detail.messages || []).map(m => ({
    role: m.role,
    content: m.content,
    sql: null,
    columns: null,
    rows: null,
  }))
}

async function createNewSession() {
  const s = await createSession('nl2sql')
  sessions.value.unshift(s)
  activeSessionId.value = s.id
  messages.value = []
}

async function deleteSession(id) {
  await delSession(id)
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (activeSessionId.value === id) {
    activeSessionId.value = sessions.value[0]?.id || null
    if (activeSessionId.value) selectSession(activeSessionId.value)
    else messages.value = []
  }
}

onMounted(async () => {
  await loadSessions()
  if (sessions.value.length) {
    activeSessionId.value = sessions.value[0].id
    await selectSession(activeSessionId.value)
  }
})

async function send() {
  if (!question.value.trim()) return
  if (!activeSessionId.value) { await createNewSession(); /* 延迟一下等 ID */ }

  const q = question.value
  messages.value.push({ role: 'user', content: q })
  question.value = ''
  loading.value = true

  try {
    // 用 nl2sql 函数，但后端需要 session_id，所以直接 fetch
    const res = await fetch(`http://localhost:8000/nl2sql`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, session_id: activeSessionId.value }),
    })
    const data = await res.json()
    messages.value.push({
      role: 'assistant',
      content: '',
      sql: data.sql,
      columns: data.columns,
      rows: data.rows,
    })
    await loadSessions()
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '请求失败：' + e.message })
  } finally {
    loading.value = false
  }
}

function getChartOption(msg) {
  const { columns, rows } = msg
  if (!columns || !rows || rows.length < 2) return null
  const numColIndices = []
  for (let j = 0; j < columns.length; j++) {
    const allNum = rows.every(row => typeof row[j] === 'number')
    if (allNum) numColIndices.push(j)
  }
  if (numColIndices.length === 0) return null
  const xData = rows.map(row => String(row[0]))
  const series = numColIndices.map(j => ({
    name: columns[j],
    type: 'bar',
    data: rows.map(row => row[j]),
  }))
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: xData },
    yAxis: { type: 'value' },
    series,
  }
}
</script>

<style scoped>
.nl2sql-layout {
  display: flex;
  height: calc(100vh - 120px);
  max-width: 1100px;
  margin: 0 auto;
  background: #f5f7fa;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.nl2sql-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
}
/* 以下完全保持原 NL2SQLChat 样式 */
.messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; font-size: 14px; }
.message-row.user .bubble { background: #4a90d9; color: #fff; border-bottom-right-radius: 4px; }
.message-row.assistant .bubble { background: #fff; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.sources pre { background: #1e1e1e; color: #d4d4d4; padding: 12px 16px; border-radius: 8px; font-size: 13px; font-family: 'Consolas','Monaco','Courier New',monospace; overflow-x: auto; white-space: pre-wrap; word-break: break-all; margin-top: 8px; }
.chart { width: 100%; height: 300px; margin-top: 12px; }
.table { margin-top: 12px; overflow-x: auto; }
.table table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table th { background: #f0f5ff; color: #4a90d9; font-weight: 600; padding: 8px 12px; text-align: left; border-bottom: 2px solid #e8e8e8; white-space: nowrap; }
.table td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
.table tbody tr:hover { background: #fafbfc; }
.table tbody tr:nth-child(even) { background: #fafafa; }
.loading-bubble { background: #fff !important; }
.dot-pulse { color: #999; font-size: 14px; }
.dot { animation: blink 1.4s infinite both; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity: 0; } 40% { opacity: 1; } }
.input-area { display: flex; gap: 10px; padding: 16px 20px; background: #fff; border-top: 1px solid #e8e8e8; border-radius: 0 0 12px 12px; }
.input-area input { flex: 1; padding: 10px 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; transition: border-color 0.2s; }
.input-area input:focus { border-color: #4a90d9; }
.input-area button { padding: 10px 24px; background: #4a90d9; color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; transition: background 0.2s; }
.input-area button:hover:not(:disabled) { background: #357abd; }
.input-area button:disabled { background: #ccc; cursor: not-allowed; }
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/view/NL2SQLChat.vue
git commit -m "feat: NL2SQLChat 接入会话侧边栏"
```

---

### 任务 11：前端 App.vue 调整布局

**文件：**
- 修改：`frontend/src/App.vue`

当前 App.vue 没有包裹层，每个组件自己管理宽高。先确认是否需要改——因为每个聊天组件内部已经用了 flex layout，App.vue 不需要额外调整。只需要确保组件的容器能正常扩展。

可选：把标题从"RAG 知识库问答"改成更有辨识度的名称，比如"RAG Forge"。

- [ ] **步骤 1：（可选）修改 App.vue 标题**

```diff
- <span class="app-title">RAG 知识库问答</span>
+ <span class="app-title">RAG Forge</span>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/App.vue
git commit -m "chore: 调整应用标题"
```

---

## 自检

1. **规格覆盖度：** 设计文档中 Phase 1 的所有要求（SQLite 存储层 + 会话 CRUD API + 前端侧边栏 + 三种模式接入）均有对应任务。
2. **占位符扫描：** 所有步骤均包含完整代码，无 TODO/占位符。
3. **类型一致性：** `database.py` 中 `create_session` 返回的 dict key 与前端使用的 key 一致，`get_sessions` 包含 `message_count`，`get_session` 返回详情不含 messages（由 `router.py` 自行合并），SSE 端点的 `session_id` 参数名与前端一致。
4. **测试覆盖：** database.py 有独立的单元测试（`test_database.py`），sessions API 有集成测试（`test_sessions_api.py`）。
