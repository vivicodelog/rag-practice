# 多会话 + 用户系统设计文档

## 概述

当前项目为单会话、无用户状态的应用。本文档设计如何升级为多会话、多用户的完整产品形态，分两阶段实施。

---

## 第一阶段：多会话（无用户）

### 目标

支持新建/切换/删除会话，每个会话独立维护对话历史，会话按功能模式（Agent/Workflow/NL2SQL）隔离。

### 1. 数据模型

#### 会话表（sessions）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| mode | TEXT | 会话模式: `agent` / `workflow` / `nl2sql` |
| title | TEXT | 会话标题，默认"新对话" |
| created_at | TEXT (ISO 8601) | 创建时间 |
| updated_at | TEXT (ISO 8601) | 最后更新时间 |

#### 消息表（messages）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 自增主键 |
| session_id | TEXT (UUID) | 外键 → sessions.id |
| role | TEXT | `user` / `assistant` |
| content | TEXT | 消息内容 |
| created_at | TEXT (ISO 8601) | 消息时间 |

#### 建表 SQL

```sql
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

CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_sessions_mode ON sessions(mode);
```

### 2. API 设计

| 方法 | 路径 | 请求体 | 返回 | 说明 |
|------|------|--------|------|------|
| POST | `/sessions` | `{"mode": "agent"}` | 新建的会话对象 | mode 必填，title 可选 |
| GET | `/sessions` | query: `?mode=agent` | 会话列表（摘要） | 按 mode 过滤 |
| GET | `/sessions/{id}` | — | 会话详情 + 消息列表 | 加载历史消息 |
| DELETE | `/sessions/{id}` | — | 成功/失败 | 连消息一起删 |
| POST | `/sessions/{id}/chat` | `{"message": "..."}` | SSE 流式/JSON | 现有 chat 逻辑，绑定会话 |

现有 `/chat` `/chat/workflow` `/nl2sql` 路由保留，但前端改为统一走 `/sessions/{id}/chat`。

### 3. 存储层设计

新增 `backend/database.py`，封装 SQLite 操作：

- `get_db()` — 获取数据库连接（单例）
- `init_db()` — 建表
- `create_session(mode, title?)` — 新建会话
- `get_sessions(mode)` — 获取会话列表
- `get_session(session_id)` — 获取会话详情
- `get_messages(session_id)` — 获取历史消息
- `save_message(session_id, role, content)` — 存消息
- `delete_session(session_id)` — 删会话 + 消息

SQLite 文件路径：`data/conversations.db`

### 4. 前端改动

当前 `App.vue` 有 4 个标签页，每个标签页内嵌一个聊天组件。

#### 新增组件

- `SessionSidebar.vue` — 左侧会话列表（新建/切换/删除）
- 在每个标签页内嵌侧边栏

#### 改动要点

- 每个标签页加载时，按 `mode` 拉取对应会话列表
- 选中会话后，加载历史消息
- 发消息时带上 `session_id`
- 删除会话后自动切到下一个会话或新建一个

### 5. 与现有代码的整合

当前 `state.py` 和 `history.py` 管理着内存中的对话历史。

改动计划：
- `state.py` 仍保留 vectordb、all_chunks、llm、reranker 等全局运行时状态
- 对话历史从内存改为 SQLite 读取
- `history.py` 的 `trim_history` 函数保持不变，入参改为从 SQLite 查到的消息列表
- Agent/Workflow/NL2SQL 的 chat 函数增加 `session_id` 参数

---

## 第二阶段：用户系统

### 目标

支持用户注册/登录，每个用户拥有独立的会话。

### 1. 用户表（users）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| username | TEXT (UNIQUE) | 用户名 |
| password_hash | TEXT | 密码哈希（bcrypt） |
| created_at | TEXT | 注册时间 |

### 2. 改动点

#### sessions 表加 user_id 字段

```sql
ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id);
```

#### 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录，返回 JWT |
| GET | `/auth/me` | 获取当前用户信息 |
| POST | `/auth/logout` | 登出 |

#### JWT 鉴权

- 登录后前端存 token（localStorage）
- 每次请求带 `Authorization: Bearer <token>`
- 后端中间件验证 token，从请求中提取 `user_id`
- 所有查询都加上 `WHERE user_id=?` 做数据隔离

#### 依赖新增

```
pyjwt
bcrypt 或 passlib[bcrypt]
```

### 3. 前端改动

- 新增 `LoginPage.vue`、`RegisterPage.vue`
- 路由守卫：未登录跳转到登录页
- API 请求统一加 token 头

---

## 非目标

- ~~MySQL 迁移~~（SQLite 完全满足当前数据量，面试不因数据库扣分）
- ~~OAuth/第三方登录~~（不需要）
- ~~权限/角色系统~~（不需要）
- ~~WebSocket~~（SSE 已够用）

---

## 实施顺序

1. 后端：`database.py` SQLite 存储层
2. 后端：会话 CRUD API
3. 后端：修改现有 chat 接口支持 `session_id`
4. 前端：SessionSidebar 组件
5. 前端：各标签页接入会话管理
6. 第二阶段：用户系统（注册/登录/JWT）
7. 第二阶段：数据隔离（会话归属用户）

---

## 自检

- [x] 数据模型覆盖了三种模式
- [x] API 设计覆盖了 CRUD
- [x] 没有 TODO 占位符
- [x] 实施顺序依赖关系正确
- [x] 非目标明确标出
- [x] SQLite → 后续加 user_id 的迁移路径清晰
