# 项目收尾三阶段 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 三阶段收尾：提交工作区改动 → 补测试覆盖 → Docker 部署

**架构：** 
- Phase A：当前改动已是最终状态，只需验证 + commit
- Phase B：tools.py 三个函数（search_docs / query_database / _rewrite_query）各自需要单元测试，agent.py 也需要测试
- Phase C：多阶段 Dockerfile 构建 + docker-compose 编排三个服务（backend / frontend / chroma）

**技术栈：** pytest (unittest.mock)、FastAPI TestClient、Docker Compose

---

## Phase A：清理并提交当前改动

### 任务 A1：验证并提交工作区改动

**文件：**
- 修改：`CLAUDE.md`
- 修改：`rag_forge/agent/workflow.py`
- 修改：`rag_forge/agent/prompts/writer.md`
- 修改：`tests/test_workflow.py`
- 修改：`backend/sse.py`
- 修改：`rag_forge/history.py`

- [ ] **步骤 1：查看完整 diff 确认改动正确**

运行：`cd d:/rag-project && git diff HEAD`

预期输出：
- `CLAUDE.md` 追加了 superpowers-zh 配置标记块
- `workflow.py` 两处改动：`history` 去掉默认值 `[]`；去掉重写循环中覆盖 answer 的那行
- `writer.md`：`{{answer}}` → `{{research}}`
- `test_workflow.py`：所有 `Workflow()` 调用补了 `history=[]`
- `sse.py`：去掉未使用的 `system_prompt` 变量
- `history.py`：删掉残留的"你的任务"注释

- [ ] **步骤 2：运行测试确保不崩**

运行：`cd d:/rag-project && python -m pytest tests/ -q --tb=short`

预期：43 passed（或更多，取决于新文件是否已加入）

- [ ] **步骤 3：提交**

```bash
cd d:/rag-project
git add CLAUDE.md rag_forge/agent/workflow.py rag_forge/agent/prompts/writer.md tests/test_workflow.py backend/sse.py rag_forge/history.py
git commit -m "chore: 提交未完成改动

- CLAUDE.md 追加 superpowers-zh 配置
- workflow.py history 改为必填参数，去掉重写覆盖 answer 的 bug
- writer.md 模板变量 {{answer}} → {{research}}
- test_workflow.py 适配 history=[] 参数
- sse.py / history.py 清理注释和死代码"
```

运行后检查：`git status` 显示工作区干净（只有未跟踪文件）

---

## Phase B：补充测试覆盖

### 任务 B1：审查已有 NL2SQL 测试文件

**文件：**
- 已存在（未跟踪）：`tests/test_nl2sql.py`
- 已存在（未跟踪）：`tests/test_nl2sql_main.py`

- [ ] **步骤 1：尝试运行 NL2SQL 测试**

运行：`cd d:/rag-project && python -m pytest tests/test_nl2sql.py tests/test_nl2sql_main.py -q --tb=short`

预期：通过或失败。如果失败分析原因（可能是 import 路径问题）。

- [ ] **步骤 2：如果测试失败，修复 import 或 mock 问题**

```
常见问题：sys.path.insert 硬编码的路径可能不匹配
修复方案：改为相对路径或确保 conftest.py 做 path 注入
```

- [ ] **步骤 3：确认测试通过后，将文件纳入 git 跟踪**

```bash
cd d:/rag-project
git add tests/test_nl2sql.py tests/test_nl2sql_main.py
```

---

### 任务 B2：编写 tools.py 测试（search_docs + query_database + _rewrite_query）

**文件：**
- 创建：`tests/test_tools.py`

- [ ] **步骤 1：编写 test_tools.py 框架**

```python
"""
tools.py 单元测试。

测试策略：
  - search_docs：mock _vectordb / _all_chunks / hybrid_search
  - query_database：mock nl2sql 函数
  - _rewrite_query：直接调函数（纯文本处理）
"""

import pytest
from unittest.mock import patch, MagicMock, ANY


class TestSearchDocs:
    """search_docs 工具测试"""

    def test_search_docs_uninitialized(self):
        """未初始化时返回错误提示"""
        from rag_forge.agent.tools import search_docs
        
        with patch("rag_forge.agent.tools._vectordb", None):
            with patch("rag_forge.agent.tools._all_chunks", []):
                result = search_docs.invoke({"query": "test"})
                assert result == "知识库尚未初始化，请先上传文档"

    def test_search_docs_no_results(self):
        """检索无结果时返回'未找到相关文档'"""
        from rag_forge.agent.tools import search_docs
        
        mock_db = MagicMock()
        mock_chunks = ["chunk1", "chunk2"]
        
        with patch("rag_forge.agent.tools._vectordb", mock_db):
            with patch("rag_forge.agent.tools._all_chunks", mock_chunks):
                with patch("rag_forge.agent.tools.hybrid_search", return_value=[]):
                    result = search_docs.invoke({"query": "不存在的内容"})
                    assert result == "未找到相关文档"

    def test_search_docs_low_score(self):
        """最高分低于 0.3 时拒绝返回"""
        from rag_forge.agent.tools import search_docs
        
        mock_db = MagicMock()
        mock_chunks = ["chunk1"]
        # 分数 0.1 < 0.3
        low_score_results = [("一些内容", 0.1, "source.txt")]
        
        with patch("rag_forge.agent.tools._vectordb", mock_db):
            with patch("rag_forge.agent.tools._all_chunks", mock_chunks):
                with patch("rag_forge.agent.tools.hybrid_search", return_value=low_score_results):
                    result = search_docs.invoke({"query": "低分查询"})
                    assert result == "未找到相关文档"
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd d:/rag-project && python -m pytest tests/test_tools.py::TestSearchDocs -v --tb=short`

预期：第一个 PASS（不依赖 mock），后两个可能 FAIL（取决于 mock path）

- [ ] **步骤 3：补 query_database 工具测试**

在 `test_tools.py` 追加：

```python
class TestQueryDatabase:
    """query_database 工具测试"""

    def test_query_database_error(self):
        """nl2sql 返回 error 时，工具返回错误信息"""
        from rag_forge.agent.tools import query_database
        
        mock_result = {
            "sql": "",
            "columns": [],
            "rows": [],
            "error": "数据库连接失败",
            "explanation": "",
        }
        
        with patch("rag_forge.agent.tools.nl2sql", return_value=mock_result):
            result = query_database.invoke({"question": "测试"})
            assert result == "数据库连接失败"

    def test_query_database_success(self):
        """正常返回时拼成易读文本"""
        from rag_forge.agent.tools import query_database
        
        mock_result = {
            "sql": "SELECT name FROM authors",
            "columns": ["姓名"],
            "rows": [["鲁迅"], ["老舍"]],
            "error": None,
            "explanation": "查询所有作者姓名",
        }
        
        with patch("rag_forge.agent.tools.nl2sql", return_value=mock_result):
            result = query_database.invoke({"question": "列出所有作者"})
            assert "SELECT name FROM authors" in result
            assert "鲁迅" in result
            assert "老舍" in result
            assert "查询所有作者姓名" in result

    def test_query_database_empty_rows(self):
        """空结果集正常处理"""
        from rag_forge.agent.tools import query_database
        
        mock_result = {
            "sql": "SELECT name FROM authors WHERE 1=0",
            "columns": ["姓名"],
            "rows": [],
            "error": None,
            "explanation": "无匹配数据",
        }
        
        with patch("rag_forge.agent.tools.nl2sql", return_value=mock_result):
            result = query_database.invoke({"question": "查询不存在的作者"})
            assert "SQL:" in result
            assert "数据：" in result
```

- [ ] **步骤 4：补 _rewrite_query 测试**

在 `test_tools.py` 追加：

```python
class TestRewriteQuery:
    """_rewrite_query 内部函数测试"""

    def test_rewrite_short_query_with_llm(self):
        """短查询（≤10字）调用 LLM 扩展"""
        from rag_forge.agent.tools import _rewrite_query
        
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "今天北京天气怎么样"
        mock_llm.invoke.return_value = mock_response
        
        with patch("rag_forge.agent.tools._llm", mock_llm):
            result = _rewrite_query("北京天气")
            assert result == "今天北京天气怎么样"

    def test_rewrite_long_query_skipped(self):
        """长查询（>10字）跳过扩展"""
        from rag_forge.agent.tools import _rewrite_query
        
        mock_llm = MagicMock()
        with patch("rag_forge.agent.tools._llm", mock_llm):
            result = _rewrite_query("今天北京的天气怎么样啊")
            # 长查询不调 LLM
            mock_llm.invoke.assert_not_called()
            assert result == "今天北京的天气怎么样啊"

    def test_rewrite_no_llm(self):
        """_llm 为 None 时跳过"""
        from rag_forge.agent.tools import _rewrite_query
        
        with patch("rag_forge.agent.tools._llm", None):
            result = _rewrite_query("天气")
            assert result == "天气"
```

- [ ] **步骤 5：运行 tools.py 全部测试**

运行：`cd d:/rag-project && python -m pytest tests/test_tools.py -v --tb=short`

预期：全部 PASS

- [ ] **步骤 6：暂存 test_tools.py**

```bash
cd d:/rag-project
git add tests/test_tools.py
```

---

### 任务 B3：编写 agent.py 测试

**文件：**
- 创建：`tests/test_agent.py`

- [ ] **步骤 1：编写 test_agent.py**

```python
"""
agent.py 单元测试。

测试策略：
  - create_llm：验证参数传递
  - build_agent：验证代理创建
"""

from unittest.mock import MagicMock, patch


class TestCreateLLM:
    """create_llm 工厂函数测试"""

    def test_create_llm_with_defaults(self):
        """不传参数时走 settings 默认值"""
        from rag_forge.agent.agent import create_llm
        
        mock_settings = MagicMock()
        mock_settings.LLM_MODEL = "deepseek-chat"
        mock_settings.LLM_TEMPERATURE = 0.7
        mock_settings.LLM_TIMEOUT = 60
        mock_settings.LLM_MAX_RETRIES = 3
        
        with patch("rag_forge.agent.agent.settings", mock_settings):
            with patch("rag_forge.agent.agent.ChatDeepSeek") as MockChat:
                create_llm(api_key="test-key")
                
                MockChat.assert_called_once_with(
                    api_key=ANY,
                    model="deepseek-chat",
                    temperature=0.7,
                    timeout=60,
                    max_retries=3,
                )

    def test_create_llm_with_overrides(self):
        """显式传参覆盖 settings"""
        from rag_forge.agent.agent import create_llm
        
        with patch("rag_forge.agent.agent.ChatDeepSeek") as MockChat:
            create_llm(
                api_key="test-key",
                model="deepseek-reasoner",
                temperature=0.0,
                timeout=120,
                max_retries=5,
            )
            
            MockChat.assert_called_once_with(
                api_key=ANY,
                model="deepseek-reasoner",
                temperature=0.0,
                timeout=120,
                max_retries=5,
            )

    def test_create_llm_secret_key(self):
        """api_key 被 SecretStr 包裹"""
        from pydantic import SecretStr
        from rag_forge.agent.agent import create_llm
        
        with patch("rag_forge.agent.agent.ChatDeepSeek") as MockChat:
            create_llm(api_key="my-secret-key")
            
            call_kwargs = MockChat.call_args[1]
            assert isinstance(call_kwargs["api_key"], SecretStr)
            assert call_kwargs["api_key"].get_secret_value() == "my-secret-key"


class TestBuildAgent:
    """build_agent 测试"""

    def test_build_agent_with_tools(self):
        """传入工具列表时创建 Agent"""
        from rag_forge.agent.agent import build_agent
        
        mock_llm = MagicMock()
        mock_tools = [MagicMock(), MagicMock()]
        
        with patch("rag_forge.agent.agent.create_agent") as MockCreate:
            result = build_agent(mock_llm, mock_tools, system_prompt="test")
            
            MockCreate.assert_called_once_with(
                mock_llm, mock_tools, system_prompt="test"
            )
```

- [ ] **步骤 2：运行测试验证**

运行：`cd d:/rag-project && python -m pytest tests/test_agent.py -v --tb=short`

预期：全部 PASS

- [ ] **步骤 3：暂存**

```bash
cd d:/rag-project
git add tests/test_agent.py
```

---

### 任务 B4：编写 sse.py 接口测试

**文件：**
- 创建：`tests/test_sse.py`

- [ ] **步骤 1：编写 test_sse.py**

```python
"""
sse.py 接口测试。

测试策略：
  - 用 FastAPI TestClient 发送请求
  - mock state 模块的全局变量
  - 测 error 分支（vectordb 未初始化），这个分支不用 mock LLM/文件
"""

import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.sse import router


class TestStreamWorkflow:
    """stream_workflow SSE 端点测试"""

    def test_vectordb_not_initialized(self):
        """vectordb 未初始化时返回 error 事件"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_state = MagicMock()
        mock_state.vectordb = None

        with patch("backend.sse.state", mock_state):
            response = client.get("/chat/workflow/stream?question=hi")

        assert response.status_code == 200
        # SSE 响应文本应包含 error 事件内容
        assert "索引未初始化" in response.text


class TestStreamAgent:
    """stream_agent SSE 端点测试"""

    def test_vectordb_not_initialized(self):
        """vectordb 未初始化时返回 error 事件"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_state = MagicMock()
        mock_state.vectordb = None

        with patch("backend.sse.state", mock_state):
            response = client.get("/chat/agent/stream?question=hi")

        assert response.status_code == 200
        assert "索引未初始化" in response.text
```

- [ ] **步骤 2：运行测试**

运行：`cd d:/rag-project && python -m pytest tests/test_sse.py -v --tb=short`

预期：PASS

- [ ] **步骤 3：暂存**

```bash
cd d:/rag-project
git add tests/test_sse.py
```

---

### 任务 B5：运行全部测试 + 汇总提交

- [ ] **步骤 1：全量运行**

运行：`cd d:/rag-project && python -m pytest tests/ -v --tb=short`

预期：全部 PASS，测试数量 43+ 新加

- [ ] **步骤 2：提交 Phase B**

```bash
cd d:/rag-project
git add tests/test_nl2sql.py tests/test_nl2sql_main.py tests/test_tools.py tests/test_agent.py tests/test_sse.py
git commit -m "test: 补充测试覆盖

- test_nl2sql.py / test_nl2sql_main.py：NL2SQL 模块测试
- test_tools.py：search_docs / query_database / _rewrite_query 测试
- test_agent.py：create_llm / build_agent 测试
- test_sse.py：SSE 流式接口测试"
```

---

## Phase C：Docker 部署

### 任务 C1：后端 Dockerfile

**文件：**
- 创建：`Dockerfile.backend`

- [ ] **步骤 1：编写 Dockerfile.backend**

```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 运行阶段 ----
FROM python:3.11-slim

WORKDIR /app

# 从 builder 复制已安装的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目代码
COPY . .

# 环境变量（可在 docker-compose 中覆盖）
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **步骤 2：确保 main.py 在根目录**

检查：`ls d:/rag-project/main.py` 存在

---

### 任务 C2：前端 Dockerfile

**文件：**
- 创建：`Dockerfile.frontend`

- [ ] **步骤 1：编写 Dockerfile.frontend**

```dockerfile
# ---- 构建阶段 ----
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY frontend/package*.json ./
RUN npm ci

# 复制源码并构建
COPY frontend/ .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine

# 复制构建产物到 Nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 配置：代理 /api 到后端
COPY <<EOF /etc/nginx/conf.d/default.conf
server {
    listen 80;
    
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }
}
EOF

EXPOSE 80
```

---

### 任务 C3：docker-compose.yml

**文件：**
- 创建：`docker-compose.yml`

- [ ] **步骤 1：编写 docker-compose.yml**

```yaml
version: "3.8"

services:
  chroma:
    image: chromadb/chroma:0.6.3
    volumes:
      - chroma_data:/chroma/chroma
    ports:
      - "8001:8000"
    environment:
      - IS_PERSISTENT=TRUE
    restart: unless-stopped

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data          # SQLite 数据持久化
      - ./chroma_db:/app/chroma_db  # Chroma 持久目录
    environment:
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:?请设置 DEEPSEEK_API_KEY 环境变量}
      - HOST=0.0.0.0
      - PORT=8000
    depends_on:
      - chroma
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  chroma_data:
```

- [ ] **步骤 2：创建 .dockerignore**

```dockerignore
__pycache__/
*.pyc
.env
.venv/
venv/
node_modules/
.git/
.gitignore
.pytest_cache/
*.md
!README.md
tests/
.claude/
docs/
chroma_db/
data/
```

---

### 任务 C4：验证 Docker 部署

- [ ] **步骤 1：构建并启动**

运行：`cd d:/rag-project && docker-compose build`

预期：构建成功无报错

- [ ] **步骤 2：启动服务**

运行：`cd d:/rag-project && DEEPSEEK_API_KEY=your_key_here docker-compose up -d`

预期：三条服务全部 running

- [ ] **步骤 3：验证健康检查**

运行：`curl http://localhost:8000/health` 或 `curl http://localhost:8000/`

预期：返回 200

- [ ] **步骤 4：验证前端**

用浏览器打开 `http://localhost:3000`，页面正常展示

- [ ] **步骤 5：提交 Phase C**

```bash
cd d:/rag-project
git add Dockerfile.backend Dockerfile.frontend docker-compose.yml .dockerignore
git commit -m "feat: Docker 部署

- Dockerfile.backend：FastAPI 多阶段构建
- Dockerfile.frontend：Vue 3 + Nginx 多阶段构建
- docker-compose.yml：backend + frontend + chroma 三服务编排
- .dockerignore：排除无需打包的文件"
```

---

## 依赖关系

```
Phase A（clean commit）
    ↓
Phase B（tests）— 依赖 A 的干净工作区
    ↓
Phase C（Docker）— 无代码依赖，可独立执行
```

如果 Phase C 因 Docker 环境问题阻塞，可以跳过 C 先完成 A+B 并推送到远程。
