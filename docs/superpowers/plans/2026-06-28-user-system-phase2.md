# 用户系统（Phase 2）实现计划

**状态：** ✅ 已完成（2026-06-28）

**目标：** 实现用户注册/登录 + JWT 鉴权 + 会话数据隔离，每个用户只能看到自己的会话。

**前置条件：** Phase 1（多会话）已全部完成并验证。

---

## 变更记录
- 初始化 RAG 时需调 `init_db()` 创建 users 表（`backend/main.py` lifespan 中已加）
- `requirements.txt` 已加 `pyjwt` + `bcrypt`
- HF 镜像环境变量 `HF_ENDPOINT=https://hf-mirror.com` 在墙内启动时需要
- 旧数据迁移：已有 sessions 数据无 user_id 字段，ALTER TABLE try/except 兼容

---

## 文件结构

### 新建
- `backend/routers/auth.py` — 注册/登录/登出/用户信息 API
- `backend/auth.py` — JWT 工具函数（生成 token、验证 token、获取当前用户依赖）
- `frontend/view/LoginPage.vue` — 登录页
- `frontend/view/RegisterPage.vue` — 注册页
- `tests/test_auth_api.py` — 注册/登录测试

### 修改
- `backend/database.py` — `init_db()` 加 `users` 表
- `backend/routers/sessions.py` — 所有查询加 `user_id` 过滤
- `backend/routers/chat.py` — chat/workflow 接口读取 `user_id`
- `backend/routers/nl2sql.py` — nl2sql 接口读取 `user_id`
- `frontend/src/api.js` — 统一加 `Authorization` 请求头
- `frontend/src/App.vue` — 路由守卫，未登录跳转登录页
- `backend/main.py` — 注册 auth 路由
- `pyproject.toml` 或 `requirements.txt` — 加 `pyjwt` + `bcrypt` 依赖

---

### 任务 1：后端 — 用户表 + 注册/登录 API

**文件：**
- 修改：`backend/database.py`
- 新建：`backend/auth.py`
- 新建：`backend/routers/auth.py`
- 修改：`backend/main.py`

#### 步骤 1：database.py — 建 users 表

`init_db()` 的 SQL 末尾追加：

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

#### 步骤 2：database.py — 新增用户 CRUD 函数

```python
def create_user(username: str, password_hash: str) -> dict
def get_user_by_username(username: str) -> dict | None
def get_user_by_id(user_id: str) -> dict | None
```

流程：uuid 生成 id，now() 记时间，INSERT 后用 `SELECT *` 回读返回 dict。

#### 步骤 3：新建 backend/auth.py — JWT 工具函数

三个函数：

- **`create_token(user_id: str) -> str`** — 用 `pyjwt` 编码，payload 放 `{"sub": user_id, "exp": ...}`，secret 用 settings 的 `JWT_SECRET`（先在 config.py 加 `JWT_SECRET: str = "your-secret-key"`，后续可改成环境变量）
- **`verify_token(token: str) -> str | None`** — 解码，成功返回 `user_id`，失败返回 `None`
- **`get_current_user(request: Request) -> str`** — FastAPI 依赖注入函数，从 `Authorization: Bearer <token>` 头提取 token → `verify_token()` → 成功返回 `user_id`，失败抛 `HTTPException(401)`。这样其他路由的 `user_id` 参数可以直接用 `Depends(get_current_user)`。

#### 步骤 4：新建 backend/routers/auth.py — 认证路由

4 个端点：

| 方法 | 路径 | 请求体 | 说明 |
|------|------|--------|------|
| POST | `/auth/register` | `{"username": "...", "password": "..."}` | bcrypt 哈希密码 → `create_user` → 返回 `{"ok": true}` |
| POST | `/auth/login` | `{"username": "...", "password": "..."}` | 查用户 → bcrypt 验密码 → `create_token(user_id)` → 返回 `{"token": "...", "user_id": "..."}` |
| GET | `/auth/me` | — | `Depends(get_current_user)` → `get_user_by_id` → 返回 `{"id", "username", "created_at"}` |
| POST | `/auth/logout` | — | 返回 `{"ok": true}`（前端删 token 即可，服务端无状态） |

注意：`/auth/register` 和 `/auth/login` 不需要 `Depends(get_current_user)`（还没登录），`/auth/me` 需要。

#### 步骤 5：main.py — 注册 auth 路由

```python
from backend.routers.auth import router as auth_router
app.include_router(auth_router)
```

---

### 任务 2：后端 — 会话数据隔离

**文件：**
- 修改：`backend/routers/sessions.py`
- 修改：`backend/routers/chat.py`
- 修改：`backend/routers/nl2sql.py`

核心思路：所有涉及 session 的操作都要知道当前用户的 `user_id`。

#### 步骤 1：sessions.py — CRUD 加 user_id 过滤

`get_sessions(mode)` 改为 `get_sessions(mode, user_id)`，SQL 加 `AND s.user_id = ?`。
`create_session(mode, user_id)` 插入时把 `user_id` 写进表。
`get_session(session_id, user_id)` 查时校验归属。
`delete_session(session_id, user_id)` 删时校验归属。

路由参数改为从 `Depends(get_current_user)` 拿 `user_id`：

```python
@router.get("")
def list_sessions(mode: str, user_id: str = Depends(get_current_user)):
    return get_sessions(mode, user_id)
```

#### 步骤 2：chat.py / nl2sql.py — chat 时带 user_id

非流式 `/chat` 和 `/chat/workflow`：从 `Depends(get_current_user)` 拿 user_id，传给 `save_message` 或会话查询。注意 `ChatRequest` 已不支持 session 创建时的 user_id 传入——session 是前端通过 `/sessions` 接口创建的，chat 端点只复用已有 session。

实际上 chat.py 不需要直接改 user_id 过滤逻辑，因为 chat 依赖一个已有的 `session_id`，而 session 的归属校验在 `/sessions` 路由层已经做了。chat 端点在存消息时也不需要 user_id——消息属于 session，session 已隔离。**如果 chat 端点不需要创建新 session，则不需要改动。**

同理 nl2sql.py 也不需改动。

所以实际需要改动的只有 `sessions.py`。

#### 步骤 3：sessions.py — 新增 user_id 处理

先改 API 参数：`create_session` 路由从 `Depends(get_current_user)` 拿 `user_id`，传给 `database.create_session(mode, title, user_id)`。

`sessions` 表加 `user_id` 字段：`ALTER TABLE sessions ADD COLUMN user_id TEXT`。但更稳妥的做法是在 `init_db()` 里加 CREATE TABLE IF NOT EXISTS，用新表结构（含 user_id 列）重建。由于 SQLite 的 `CREATE TABLE IF NOT EXISTS` 不会覆盖已有表，需要执行 `ALTER TABLE ... ADD COLUMN` 来补列：

```python
conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
```

但 `ALTER TABLE ADD COLUMN` 在列已存在时会报错。推荐用 try/except 包一下：

```python
try:
    conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id)")
except sqlite3.OperationalError:
    pass  # 列已存在
```

---

### 任务 3：前端 — 登录/注册页面 + token 管理

**文件：**
- 新建：`frontend/view/LoginPage.vue`
- 新建：`frontend/view/RegisterPage.vue`
- 修改：`frontend/src/api.js`
- 修改：`frontend/src/App.vue`

#### 步骤 1：api.js — 加 auth 请求方法 + token 拦截

新增函数：
- `login(username, password)` → POST `/auth/login`，存 token 到 localStorage
- `register(username, password)` → POST `/auth/register`
- `getMe()` → GET `/auth/me`，需要 Authorization 头
- `logout()` → POST `/auth/logout`，删 localStorage token

在 `fetch` 封装里统一加 Authorization 头（如果 localStorage 有 token）：

```javascript
function authHeaders() {
  const token = localStorage.getItem('token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}
```

每个请求的 `headers` 里 `...authHeaders()` 展开。

#### 步骤 2：LoginPage.vue — 登录页

两个输入框（用户名、密码）+ 登录按钮 + 注册链接。

登录成功 → 存 token → 切换到主界面（tab='chat'），通过 emit 或路由事件通知 App.vue。

#### 步骤 3：RegisterPage.vue — 注册页

两个输入框 + 注册按钮 + 返回登录链接。

注册成功 → 提示"注册成功" → 切回登录页。

#### 步骤 4：App.vue — 路由守卫

核心逻辑：

```javascript
const loggedIn = ref(!!localStorage.getItem('token'))

// 如果没登录且当前不在登录/注册页，显示登录页
const showLogin = computed(() => !loggedIn.value && tab.value !== 'register')
```

登录后设置 `loggedIn.value = true`。

登出或 token 过期时清除 token 并回到登录页。

注：`/auth/me` 可在 App.vue `onMounted` 时调一次，验证 token 是否有效。如果返回 401，清除 token 并回到登录页。

---

## 自检

1. **依赖完整性：** `pyjwt` + `bcrypt` 是否已加入 requirements.txt/pyproject.toml？
2. **数据迁移：** 已有 sessions 数据没有 user_id，`get_sessions` 加了 `WHERE user_id=?` 后旧数据查不出来。要么给旧数据补 user_id，要么 migration 脚本统一处理。
3. **前端 token 过期：** JWT 有过期时间（建议 7 天），过期后 API 返回 401，前端需要跳回登录页。
4. **密码安全：** bcrypt 自动处理 salt，不用自己加盐。
5. **测试：** 注册 → 登录拿 token → 带 token 查 sessions → 不带 token 查 sessions 报 401。这组流程需要写测试。
