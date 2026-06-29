# 📚 RAG 智能问答系统

基于 **LangChain + DeepSeek + ChromaDB + FastAPI + Vue 3** 的本地知识库问答系统。

上传文档后，AI 会自动从文档中检索相关内容来回答问题。支持**单 Agent 模式**、**多角色 Workflow 模式**（Researcher → Writer → Reviewer）和**NL2SQL**。

---

## ✨ 功能

### 问答
- ✅ **Agent 模式** — LLM 自主选择工具（搜文档/查数据库/查天气），不固定流程
- ✅ **Workflow 模式** — Researcher 搜索 → Writer 写作 → Reviewer 审查，不通过则自动重写（最多 2 次）
- ✅ **SSE 流式推送（Agent + Workflow）** — token 级实时推送，前端打字机效果；工具调用过程可见
- ✅ **混合检索** — 向量语义搜索 + jieba 关键词匹配，结果更精准
- ✅ **工具调用** — `search_docs`（文档搜索）+ `query_database`（数据库查询）+ `get_weather`（天气查询），可扩展
- ✅ **来源标注** — 回答附带文档来源和匹配度分数
- ✅ **NL2SQL** — 自然语言转 SQL，查询后返回结果表格 + 可解释性说明
- ✅ **NL2SQL 注册为 Agent 工具** — 在 RAG 对话中直接查 SQLite 数据库，LLM 自主选择 query_database 工具
- ✅ **多轮对话** — Agent / Workflow / NL2SQL 均支持上下文记忆，历史消息自动拼入 prompt

### 用户与会话
- ✅ **多会话管理** — 新建/切换/删除会话，三种模式独立会话，SQLite 持久化
- ✅ **用户系统** — JWT 登录/注册（bcrypt 密码加密），会话数据按用户隔离
- ✅ **会话侧边栏** — 每个页面左侧会话列表，支持新建/删除/切换

### 文档管理
- ✅ **上传文档** — 支持 TXT / PDF / DOCX / MD，自动构建知识库
- ✅ **删除文档** — 可删除已有文档，向量库自动重建
- ✅ **文档列表** — 查看已上传文档的名称、大小、上传时间

### 评测
- ✅ **三模式对比** — 单 Agent vs Workflow（无审查）vs Workflow（有审查）
- ✅ **LLM-as-Judge 打分** — 准确率 / 来源命中率 / 回答完整度 三项指标

---

## 🖥️ 界面

四个标签页，统一登录后使用：

| 标签 | 说明 |
|------|------|
| **💬 问答(Agent)** | 单 Agent 气泡对话，直接提问 |
| **💾 数据库** | NL2SQL 自然语言转 SQL，查询结果表格展示 + 可解释性说明 |
| **🔁 工作流** | Workflow 模式，实时展示研究员→写作者→审查员的执行过程和最终答案 |
| **📁 文档管理** | 上传/删除文档，管理知识库 |

每个页面左侧有**会话侧边栏**，支持新建/切换/删除会话。

首次使用需**注册账号**，登录后会话数据按用户隔离。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件（已存在则跳过）：

```
DEEPSEEK_API_KEY=你的deepseek_api_key
JWT_SECRET=你的jwt密钥（可选，默认有内置密钥）
```

> 前往 [DeepSeek 官网](https://platform.deepseek.com/) 注册获取 API Key

### 3. 启动后端

```bash
python -m backend.main
```

默认监听 `http://localhost:8000`，启动日志会显示初始化过程和文档加载情况。

### 4. 启动前端（新窗口）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`，**先注册账号，登录后使用**。

### 5. 上传文档

首次使用，在 **文档管理** 标签页上传你的文档（TXT / PDF / DOCX / MD），系统会自动构建知识库，之后就可以在问答页面提问了。

### 6. Docker 部署

```bash
docker-compose up --build
```

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`

### 7. 旧版 Gradio（可选）

```bash
python rag_app.py
```

浏览器自动打开 `http://localhost:7860`

---

## 📁 项目结构

```
rag-project/
├── rag_app.py              # Gradio 版主程序（旧版保留）
├── requirements.txt        # 依赖清单
├── .env                    # API 密钥（不提交到 Git）
├── CLAUDE.md               # 项目说明 + AI 辅助规范
├── AI_ASSISTANT_PLAN.md    # Workflow 构建计划（学习路线图）
├── Dockerfile.backend      # 后端容器构建
├── Dockerfile.frontend     # 前端容器构建
├── docker-compose.yml      # Docker 编排（后端 + 前端）
│
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口（lifespan 初始化）
│   ├── router.py           # API 路由统一入口（委托到 routers/）
│   ├── auth.py             # JWT 创建/验证工具函数
│   ├── database.py         # SQLite 会话存储层
│   ├── sse.py              # SSE 流式推送（Agent + Workflow 实时事件）
│   ├── schemas.py          # 请求/响应数据模型
│   ├── state.py            # 运行时全局状态
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py         # 注册/登录 API
│   │   ├── chat.py         # Agent / Workflow 聊天
│   │   ├── documents.py    # 上传/删除/文档列表/健康检查
│   │   ├── nl2sql.py       # NL2SQL 查询
│   │   └── sessions.py     # 会话 CRUD
│
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── App.vue         # 主页面（登录/注册 + 四标签切换）
│   │   ├── api.js          # 后端接口封装（含 token 注入）
│   │   └── main.js         # 入口
│   ├── view/               # 页面组件
│   │   ├── ChatView.vue    # Agent 模式气泡对话（SSE 流式）
│   │   ├── WorkflowChat.vue# Workflow 模式（步骤展示 + SSE 实时更新）
│   │   ├── NL2SQLChat.vue  # NL2SQL 查询页（表格 + 可解释性）
│   │   ├── DocManager.vue  # 文档管理
│   │   ├── LoginPage.vue   # 登录页
│   │   └── RegisterPage.vue# 注册页
│   ├── components/
│   │   ├── SessionSidebar.vue # 会话侧边栏
│   │   └── HelloWorld.vue  # 示例组件
│   └── package.json
│
├── rag_forge/              # RAG 核心逻辑
│   ├── service.py          # 公共服务层（向量库重建等）
│   ├── config.py           # 配置管理（含 JWT_SECRET）
│   ├── agent/
│   │   ├── agent.py        # Agent 封装 + create_llm 工厂
│   │   ├── tools.py        # 工具定义（search_docs / query_database / get_weather / review_result）
│   │   ├── workflow.py     # Workflow 编排核心（run + stream）
│   │   └── prompts/
│   │       ├── researcher.md  # 研究员提示词
│   │       ├── writer.md      # 写作者提示词
│   │       └── reviewer.md    # 审查员提示词
│   ├── data/               # 文档加载和切分
│   ├── embedding/          # 本地嵌入模型
│   ├── retrieval/          # 混合检索（向量 + jieba 关键词）
│   ├── evaluation/         # 评测体系（LLM-as-Judge 三模式对比）
│   └── ui/                 # Gradio UI 组件
│
├── nl2sql/                 # NL2SQL 模块
│   └── agent.py            # NL2SQL Agent（自愈循环 + 可解释性）
│
├── data/                   # 文档存放目录
│   └── manifest.json       # 文档清单
├── chroma_db/              # 向量数据库（自动生成）
├── scripts/
│   └── eval_workflow.py    # 评测入口脚本
└── tests/                  # 单元测试
    ├── conftest.py         # 测试共用夹具
    ├── test_agent.py
    ├── test_database.py
    ├── test_history.py
    ├── test_hybrid.py
    ├── test_keyword.py
    ├── test_loader.py
    ├── test_nl2sql.py
    ├── test_nl2sql_main.py
    ├── test_reranker.py
    ├── test_sessions_api.py
    ├── test_sse.py
    ├── test_tools.py
    ├── test_vector.py
    └── test_workflow.py
```

---

## 🧠 技术架构

### Agent 模式

```
用户提问
    │
    ▼
FastAPI → LLM（绑 search_docs / query_database / get_weather）
    │
    ▼
┌─ Agent 循环（最多 3 轮）──────────────┐
│  LLM 自主判断 → 调工具 → 执行 → 看结果 │
│        ↕                              │
│   search_docs（混合检索 ChromaDB + jieba）│
│   query_database（NL2SQL → SQLite）     │
│   get_weather（wttr.in 天气 API）       │
└──────────────────────────────────────┘
    │
    ▼
返回 JSON → Vue 前端渲染（气泡 + 来源标签）
```

### Workflow 模式

```
用户提问
    │
    ▼
┌─ Researcher ──────────────────────────┐
│  调 search_docs 搜索知识库            │
│  整理研究发现（摘要 + 要点）           │
└──────────────┬───────────────────────┘
               ▼
┌─ Writer ──────────────────────────────┐
│  基于研究发现组织答案                  │
│  标注信息来源                         │
└──────────────┬───────────────────────┘
               ▼
┌─ Reviewer ────────────────────────────┐
│  检查：事实性 / 来源标注 / 编造 / 相关 │
│            │                          │
│      ┌─────┴─────┐                   │
│     通过        不通过                 │
│      │           │                    │
│      ▼           ▼                    │
│   完成答案   Writer 重写（最多 2 次）  │
│               │                      │
│               ▼                      │
│          重新审查                     │
└──────────────────────────────────────┘
    │
    ▼
SSE 流式推送 → Vue 前端实时展示步骤状态 + 最终答案
```

### 用户系统

```
注册 → POST /api/auth/register → bcrypt 哈希 → 写入 SQLite users 表
登录 → POST /api/auth/login   → 校验密码 → 签发 JWT（7天有效）
鉴权 → 前端带 Authorization: Bearer <token> → 后端 verify_token → 路由到对应用户的会话
```

---

## ⚙️ 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 前端框架 | Vue 3 + Vite |
| 大模型 | DeepSeek Chat / Claude |
| 向量数据库 | ChromaDB |
| 嵌入模型 | BAAI/bge-small-zh-v1.5（本地运行） |
| AI 框架 | LangChain |
| 中文分词 | jieba |
| 认证 | JWT + bcrypt |
| 评测 | LLM-as-Judge |
| 容器化 | Docker + docker-compose |
| 旧版界面 | Gradio |

---

## 📝 说明

- 嵌入模型已在本地缓存（ModelScope 下载），无需联网即可使用
- 所有文档处理在本地完成，文档内容不会上传到第三方
- 如果添加文档后知识库没有更新，调 `GET /health` 查看状态
- Workflow 模式通过 SSE（Server-Sent Events）实时推送执行状态，前端无需轮询
- 用户登录后才可使用所有功能，会话数据按用户隔离

---

## 📊 评测结果

| 模式 | 准确率 | 来源命中率 | 回答完整度 |
|------|:------:|:---------:|:---------:|
| 单 Agent | 4.3 | 3.4 | 4.3 |
| Workflow（无审查） | 4.3 | 3.9 | 4.3 |
| Workflow（有审查） | **4.7** | **4.7** | **4.7** |

- 单 Agent 来源命中率最低 — 容易不写来源
- Workflow 的 Researcher 天然记录搜索来源，提升了来源质量
- 有 Reviewer 全面最优 — 审查循环确实提升了回答质量

---

## 🔜 后续优化方向

- ✅ Agent 改造：LLM 自主选择工具（search_docs / get_weather）
- ✅ Workflow 编排：Researcher → Writer → Reviewer 多角色协作
- ✅ SSE 实时推送：前端可视化展示思考过程
- ✅ 评测体系：三模式对比 + LLM-as-Judge 打分
- ✅ 多轮对话支持
- ✅ NL2SQL 注册为 Agent 工具 — RAG 对话里可以直接查数据库
- ✅ 多会话管理 Phase 1 — SQLite 存储 + CRUD API + SessionSidebar
- ✅ 用户系统 Phase 2 — JWT 登录/注册 + bcrypt + 会话数据隔离
- ✅ Docker 部署 — FastAPI + Vue + Chroma 容器化
- [ ] 支持更多工具（网络搜索、代码执行等）
- [ ] 测试覆盖率补全（test_auth_api.py）
- [ ] 旧文件清理（NL2SQLChat.vue 已迁移等）
- [ ] 管理后台（用户管理、用量统计）
