# 项目收尾三阶段规格

## 概述

将当前工作区的未提交修改、测试覆盖缺口、Docker 部署三步收尾，按顺序完成，每步可独立验证。

---

## Phase A：清理并提交当前改动

**目标：** 提交工作区所有未完成修改，得到一个干净的起点。

### 改动清单

| 文件 | 改动 | 说明 |
|------|------|------|
| `CLAUDE.md` | 追加 superpowers-zh 配置标记块 | 框架自动注入 |
| `rag_forge/agent/workflow.py` | `history` 改为必填参数（去掉默认 `[]`） | 避免意外共享默认列表 |
| `rag_forge/agent/workflow.py` | 去掉重写循环中 `results["answer"] = results.get("research_data")` | 该行会错误覆盖重写后的答案 |
| `rag_forge/agent/prompts/writer.md` | `{{answer}}` → `{{research}}` | 模板变量名与实际结果 key 对齐 |
| `tests/test_workflow.py` | 所有 `Workflow()` 调用补上 `history=[]` | 适配必填参数变更 |
| `backend/sse.py` | 去掉未使用的 `system_prompt` 读取代码 | 清理死代码 |
| `rag_forge/history.py` | 删掉残留的"你的任务"注释 | 清理教学痕迹 |

### 验收标准
- `git status` 显示工作区干净（除了未跟踪的新测试文件）
- `pytest tests/` 全部通过

---

## Phase B：补充测试覆盖

**目标：** 补全核心模块的单元测试，提升覆盖率。

### 现有测试（43 个）
```
test_history.py      — trim_history 单元测试
test_hybrid.py       — 混合检索
test_keyword.py      — 关键词检索
test_loader.py       — 文档加载
test_nl2sql.py       — 新文件，待审查
test_nl2sql_main.py  — 新文件，待审查
test_reranker.py     — Reranker
test_vector.py       — 向量检索
test_workflow.py     — Workflow 编排
```

### 待补测试

| 模块 | 测试内容 | 优先级 |
|------|---------|--------|
| `rag_forge/agent/tools.py` | `search_docs`（正常/空结果/低分过滤） | 高 |
| `rag_forge/agent/tools.py` | `query_database`（正常/错误/空结果） | 高 |
| `rag_forge/agent/tools.py` | `_rewrite_query`（短查询扩展/长查询跳过） | 中 |
| `backend/sse.py` | `stream_agent` / `stream_workflow` 端点 | 中 |
| `rag_forge/agent/agent.py` | Agent 创建/工具绑定 | 中 |

### 验收标准
- `pytest tests/` 全部通过
- 核心模块（tools.py、agent.py）测试覆盖
- 新 NL2SQL 测试文件审查通过并入测试套件

---

## Phase C：Docker 部署

**目标：** 写 Dockerfile + docker-compose.yml，一条命令启动。

### 架构方案

```
docker-compose up
├── backend     — FastAPI 应用（Dockerfile）
├── frontend    — Vue 3 + Nginx 静态服务（Dockerfile）
└── chroma      — Chroma 向量库（chromadb/chroma 镜像）
```

### 组件详情

**后端 Dockerfile：**
- base: `python:3.11-slim`
- 安装系统依赖：SQLite + 中文分词编译依赖
- pip install -r requirements.txt
- uvicorn 启动，端口 8000

**前端 Dockerfile：**
- build stage: node:20 → npm build
- run stage: nginx:alpine → 复制 dist 到 `/usr/share/nginx/html`
- 代理 `/api` 到后端

**docker-compose.yml：**
- 三个 service：backend、frontend、chroma
- backend 依赖 chroma
- 数据持久卷：chroma 数据、SQLite 文件
- 环境变量配置

### 验收标准
- `docker-compose up` 启动无报错
- 前端页面正常展示
- 搜索/问答功能可用

---

## 依赖关系

```
Phase A ──→ Phase B ──→ Phase C
  提交清理     补测试     打包部署
```

Phase A 无外部依赖，最先执行。
Phase B 依赖 Phase A 的干净工作区。
Phase C 无代码依赖，但放在最后做最合理。

---

## 风险 / 边界情况

- **Phase B**：`sse.py` 测试依赖 FastAPI TestClient，需要确保 `state` 模块在测试中正确初始化
- **Phase C**：Windows 下 docker-compose 路径挂载可能有格式问题，需要验证；Chroma 镜像版本需固定
- 如果中间遇到阻塞（如 Docker 环境问题），可以跳过 Phase C 先完成 A+B 并提交
