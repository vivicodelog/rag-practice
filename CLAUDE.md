# RAG Project

## 项目定位
AI 知识库问答助手，RAG + Agent + Workflow 全栈项目。

## 技术栈
- **后端**：FastAPI + LangChain + Chroma（向量库）
- **前端**：Vue 3（分离部署）
- **Agent**：bind_tools 模式（LLM 自主选工具）
- **Workflow**：Researcher → Writer → Reviewer 轻量编排

## 用户背景
- 前端 5 年（Vue），全脱产转 AI 大模型应用岗
- Python / AI 是增量，前端是基本盘
- **教学模式**：先拆步骤，再一句一句带着写，每行解释为什么，最后复盘
- 回答简短有重点，不吹牛
- 前端默认已掌握，不需要解释基础概念

## 当前学习重点（2026-06-23）
- ✅ 已跑通：FastAPI + Vue 分离、单 Agent（bind_tools）、Service 层
- ✅ 已跑通：Workflow 编排（Researcher → Writer → Reviewer）
- ✅ 已跑通：NL2SQL 三阶段（SQLite → Agent → column_meta → 前端展示 + 自愈循环 + 可解释性）
- ✅ 已跑通：多轮对话历史公共模块（history.py + create_llm()），覆盖 RAG/Workflow/NL2SQL
- 🚧 待做：测试覆盖率、NL2SQL 注册为 Agent 工具、Docker 部署

## 关键文件索引
| 文件 | 说明 |
|------|------|
| `rag_forge/service.py` | 核心业务（搜索、重建等） |
| `rag_forge/history.py` | 多轮对话历史压缩（trim_history） |
| `rag_forge/agent/agent.py` | Agent 封装 + create_llm 工厂 |
| `rag_forge/agent/workflow.py` | Workflow 编排 |
| `rag_forge/agent/tools.py` | Agent 工具定义 |
| `rag_forge/agent/prompts/` | 各角色 system prompt |
| `backend/router.py` | API 路由 |
| `backend/state.py` | 应用状态 |
| `backend/schemas.py` | Pydantic 模型 |
| `backend/sse.py` | SSE 流式推送 |
| `nl2sql/agent.py` | NL2SQL Agent |
| `tests/` | 单元测试目录 |

## 远程仓库
| 平台 | URL | 协议 |
|------|-----|------|
| GitHub (`origin`) | `https://github.com/vivicodelog/rag-practice.git` | **HTTP** |
| Gitee (`gitee`) | `git@gitee.com:zhanghui330/rag-practice.git` | **SSH** |

## 代码风格
- Python：类型注解 + 简短注释
- Vue：Options API + `<script setup>`
- 测试：pytest + 覆盖率
