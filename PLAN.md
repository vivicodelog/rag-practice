# 🔨 RAG-Forge 锻造计划

> 在 `rag_app.py` 同一个项目里，逐步构建模块化进阶版本。
> 两个都在 `rag-project/` 下，方便随时对比。

## 为什么在同一个项目里？

| 旧版 | 进阶版 |
|------|--------|
| `rag_app.py`（单文件 600+ 行） | `rag_forge/`（模块拆分） |
| 所有文件切 300 字 | 按类型自适应切分 |
| 向量+关键词硬拼接 | 归一化分数 + Rerank 精排 |
| `print()` 看日志 | 结构化日志 + Trace |
| 人肉评估 | 评测集自动跑分 |

**共用** `.env`、`data/`、`chroma_db/`，嵌入模型也不用重新下载。

---

## Phase 0：脚手架（✅ 已完成）

```
rag-project/
├── rag_app.py              # 旧版单文件
├── rag_forge/               # 新版模块 ← 你要填代码的地方
│   ├── config.py            # 统一配置
│   ├── data/
│   │   ├── manifest.py      # 文档清单
│   │   └── loader.py        # 文档加载 + 切分
│   ├── embedding/
│   │   └── embed.py         # 嵌入模型
│   ├── retrieval/
│   │   ├── vector.py        # 向量检索
│   │   ├── keyword.py       # 关键词检索
│   │   ├── hybrid.py        # 混合检索
│   │   └── reranker.py      # [Phase 2] 重排序
│   ├── agent/
│   │   ├── tools.py         # 工具函数
│   │   └── agent.py         # 代理 + 对话
│   ├── ui/
│   │   └── app.py           # Gradio 界面
│   └── utils/
│       └── logger.py        # 日志工具
├── data/                    # 共用文档
├── chroma_db/               # 共用向量库
├── tests/                   # [Phase 4] 测试
└── PLAN.md                  # ← 你正在看的这份计划
```

---

## Phase 1：核心流程（对标 rag_app.py）

目标：用模块化的方式，实现和 `rag_app.py` 一样的功能。

### Step 1 — 实现 config.py

对照旧项目，把散落的常量集中到 `Settings` 类里。

**开放 `rag_app.py` 搜索这些值：**
- `DATA_DIR = "data"`、`MANIFEST_FILE`、`SYNC_STATE_FILE`
- `model_name=`, `model_kwargs`, `encode_kwargs`
- `chunk_size=300`, `chunk_overlap=30`
- `search_kwargs={"k": 6}`
- `model="deepseek-chat"`, `temperature=0.7`
- `MAX_ROUNDS = 4`

**你的任务：** 把这些值填入 `rag_forge/config.py` 的 `Settings` 类。

**验证：**
```python
python -c "from rag_forge.config import settings; print(settings.DATA_DIR)"
# 应该输出 data
```
#300
---

### Step 2 — 实现 embedding/embed.py

打开 `rag_app.py`，找到 HuggingFaceEmbeddings 初始化那段代码，复制到 `embed.py` 的 `create_embeddings()` 里。

```python
def create_embeddings(...):
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL_PATH,
        model_kwargs={"device": settings.EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": settings.EMBEDDING_NORMALIZE},
    )
```

**验证：**
```python
python -c "from rag_forge.embedding.embed import create_embeddings; e = create_embeddings(); print(type(e).__name__)"
# 应该输出 HuggingFaceEmbeddings
```
<!-- #Loading weights: 100%|█████████████████████████████████████████████████████| 71/71 [00:00<00:00, 34467.08it/s]
HuggingFaceEmbeddings -->
---

### Step 3 — 实现 data/manifest.py

打开 `rag_app.py`，把 `load_manifest()`、`save_manifest()`、`sync_manifest()` 三个函数复制过来。注意参数从全局变量改成传参。

**你的任务：**
- `load_manifest(manifest_file)` → 原来是不传参的，现在要接受参数
- `save_manifest(manifest, manifest_file)` → 同理
- `sync_manifest(data_dir, manifest_file)` → 同理

**验证：**
```python
python -c "from rag_forge.data.manifest import sync_manifest; from rag_forge.config import settings; print(sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE))"
# 应该打印文档列表
```
暂时返回58个文档
---

### Step 4 — 实现 data/loader.py

打开 `rag_app.py`，把 `build_vectorstore()`、`need_rebuild()` 复制过来。同样改成传参。

核心逻辑不变，区别：
1. 函数参数从全局变量改成传参
2. 切分策略可以保留单一的 `RecursiveCharacterTextSplitter`（以后再加类型区分）
3. chunks.json 的保存逻辑保留

**验证：**
```python
python -c "
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.manifest import sync_manifest
from rag_forge.data.loader import build_vectorstore

embeddings = create_embeddings()
vectordb = build_vectorstore(settings.DATA_DIR, settings.CHROMA_DIR, embeddings)
print('向量库构建完成')
"
```

---

### Step 5 — 实现 retrieval/ 三个模块

**5a. retrieval/vector.py**
从 `rag_app.py` 的 `search_docs` 函数中，把向量检索部分抽出来：
```python
def vector_search(query, vectordb, top_k=6):
    results = vectordb.similarity_search_with_score(query, k=top_k)
    # 把 L2 距离转成 0~1 的分数
    # 返回 [(content, score, source)]
```

**5b. retrieval/keyword.py**
从 `search_docs` 中把 jieba 关键词匹配部分抽出来：
```python
def keyword_search(query, all_chunks, top_k=10):
    # jieba 分词 → 关键词匹配 → 分数 = 命中字数/总字数
    # 返回 [(content, score, source)]
```

**5c. retrieval/hybrid.py**
调用上面两个，合并排序：
```python
def hybrid_search(query, vectordb, all_chunks, top_k=6, reranker=None):
    vector_results = vector_search(query, vectordb, top_k*2)
    kw_results = keyword_search(query, all_chunks, top_k*2)
    # 合并去重，按分数降序
    # 返回 top_k 条
```

**这三个文件是 rag_forge 的核心，值得花时间理解清楚。**

**验证：**
```python
python -c "
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore
from rag_forge.retrieval.hybrid import hybrid_search

embeddings = create_embeddings()
source = FileSource(settings.DATA_DIR)
vectordb, all_chunks = build_vectorstore(source, embeddings, settings.CHROMA_DIR)

results = hybrid_search('跨域', vectordb, all_chunks)
for content, score, source in results[:3]:
    print(f'[{score:.2f}] [{source}] {content[:50]}...')
"

```
Prefix dict has been built successfully.
---

### Step 6 — 实现 agent/ 两个模块

**6a. agent/tools.py**
```python
@tool
def get_weather(city: str) -> str:
    # 从 rag_app.py 复制

@tool  
def search_docs(query: str) -> str:
    # 调用 hybrid_search，格式化输出
    # 这里需要访问 vectordb 和 all_chunks，用全局变量或闭包
```

关于 `vectordb` 和 `all_chunks` 的访问：
- 最简单的做法：在 `tools.py` 模块顶部声明全局变量，在 `app.py` 启动时赋值
- 进阶做法：用依赖注入或闭包函数

**6b. agent/agent.py**
```python
def create_llm(...):
    # 从 rag_app.py 复制 ChatDeepSeek 初始化代码

def build_agent(llm, tools, system_prompt):
    # 从 rag_app.py 复制 create_agent 调用

def chat(message, history, agent, max_rounds=4):
    # 复制 chat_fn 的逻辑（历史压缩 + 流式输出）
```

---

### Step 7 — 实现 ui/app.py

把 `rag_app.py` 中 Gradio UI 的部分（从 `CUSTOM_CSS` 到 `demo.launch`）复制过来。

**变化点：**
1. 导入路径改为 `from rag_forge.xxx import xxx`
2. 文档管理函数（上传/删除/刷新）可以继续写在 `app.py` 里，或单独抽到 `data/` 模块
3. 启动函数改成 `main()`

---

### ✅ Phase 1 完成

```
启动：python -m rag_forge.ui.app
功能：上传文档 → 问答 → 和 rag_app.py 表现一致
结构：代码分散在多个文件，每个文件不超 200 行
```

---

## Phase 2：Rerank 重排序 🚀

（从这一步开始，旧项目 rag_app.py 做不到了）

### 前置：安装依赖

```bash
pip install sentence-transformers  # 已经装了
# CrossEncoder 在 sentence-transformers 里自带了
```

### 实现 retrieval/reranker.py

```python
from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name="BAAI/bge-reranker-v2-m3"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list, top_k: int = 3):
        """对候选项打分并重新排序"""
        pairs = [(query, content) for content, _, _ in candidates]
        scores = self.model.predict(pairs)
        # 合并分数，按新分数降序排列
        result = []
        for i, (content, _, source) in enumerate(candidates):
            result.append((content, float(scores[i]), source))
        result.sort(key=lambda x: -x[1])
        return result[:top_k]
```

### 修改 hybrid.py

```python
def hybrid_search(query, vectordb, all_chunks, top_k=6, reranker=None):
    # 1. 向量搜索 Top-15
    # 2. 关键词匹配 Top-15
    # 3. 合并去重
    # 4. 如果有 reranker: rerank → 取 top_k
    # 5. 否则: 按归一化分数排序 → 取 top_k
```

### 修改 config.py

```python
RERANK_ENABLED = True  # 改成 True
```

### 对比效果

```
同一问题 "前后端跨域怎么解决"
→ 加 Rerank 前：回答可能混入不相关的内容
→ 加 Rerank 后：Top-3 更精准，回答质量明显提升
```

---

## Phase 3：评测体系 📊

（等 Phase 2 做完再做，正好对比效果）

### Step 1：建评测集

```python
# tests/eval_dataset.json
[
    {
        "question": "什么是跨域？",
        "reference_docs": ["dictionary.pdf"],
        "category": "概念理解"
    },
    ...
]
```

从你的文档里挑 10-20 个 Q&A 对就行。

### Step 2：评测脚本

```python
# scripts/evaluate.py
def evaluate():
    dataset = load_eval_dataset()
    results = []
    for item in dataset:
        answer = ask_question(item["question"])
        # 检查来源文档是否在 reference_docs 中
        doc_hit = check_source(answer, item["reference_docs"])
        results.append({
            "question": item["question"],
            "doc_hit": doc_hit,
            "answer": answer
        })
    # 统计命中率
    hit_rate = sum(r["doc_hit"] for r in results) / len(results)
    print(f"来源命中率：{hit_rate:.1%}")
```

### Step 3：对比实验

```
第一次跑：RERANK_ENABLED = False → 记录命中率
第二次跑：RERANK_ENABLED = True  → 记录命中率
对比：Rerank 提升了多少？
```

---

## Phase 4：生产级打磨 🔧

### 4.1 增量更新（✅ 已完成）

核心改动：
1. `loader.py` 新增 `get_file_md5s()` — 计算每个文件的 MD5
2. `build_vectorstore()` 新增 `old_state` 参数 — 增量模式下只处理有变化的文件
3. 上传/删除文件时，对比 MD5 → 只删除/添加变了的块，不动其他
4. sync_state.json 现在记录每个文件的 MD5 指纹

### 4.2 结构化日志

```bash
pip install loguru
```

步骤：
1. 在 `app.py` 启动入口加一行配置：
   ```python
   from loguru import logger
   logger.add("rag_forge.log", rotation="10 MB", level="INFO")
   ```
   之后所有 `logger.info()` 同时写入终端 + `rag_forge.log` 文件。

2. 逐步把 `print()` 替换为 `logger.info()` / `logger.error()` / `logger.warning()`

3. （可选）每次问答生成 `trace_id`，串联检索 → 生成全流程：
   ```
   2026-06-05 14:30:01 | [trace_001] 收到用户问题
   2026-06-05 14:30:02 | [trace_001] hybrid_search 返回 6 条结果
   2026-06-05 14:30:04 | [trace_001] LLM 回答完成
   ```
   出问题时 `grep trace_001 rag_forge.log` 就能看到完整流水。

### 4.3 单元测试

在 `tests/` 目录下写 pytest 测试。

**准备工作：**
```bash
pip install pytest
```

**创建 `tests/test_retrieval.py`**，写 3 个简单测试：

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_forge.retrieval.vector import vector_search
from rag_forge.retrieval.keyword import keyword_search
from rag_forge.retrieval.hybrid import hybrid_search


def test_vector_returns_list():
    """向量检索返回的是列表"""
    results = vector_search("测试", vectordb, top_k=3)
    assert isinstance(results, list)


def test_keyword_finds_match():
    """关键词能搜到确定内容"""
    results = keyword_search("跨域", all_chunks, top_k=3)
    assert len(results) > 0


def test_hybrid_not_empty():
    """混合检索不返回空"""
    results = hybrid_search("测试", vectordb, all_chunks, top_k=3)
    assert len(results) > 0
```

**运行测试：**
```bash
cd d:/rag-project
pytest tests/ -v
```

**注意：**
- `vectordb` 和 `all_chunks` 需要先在测试文件里初始化（参考 `runner.py` 的 `init_rag()`）
- 如果嫌慢，可以只测 keyword（不需要加载 embedding 模型）

### 4.4 文档类型自适应切分

当前所有文件都用 300 字固定切分，改成按文件类型用不同策略。

**实现思路：**
1. 在 `data/loader.py` 里加一个函数，根据文件后缀选切分器
2. 不同类型的文件用不同参数

```python
def get_splitter(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "md":
        from langchain.text_splitter import MarkdownHeaderTextSplitter
        return MarkdownHeaderTextSplitter(headers_to_split_on=[("##", "章节")])
    elif ext == "pdf":
        return RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    else:  # txt, docx, 代码等
        return RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
```

然后在 `build_vectorstore()` 里对每个文件调用 `get_splitter(file.filename)` 来切分。

**验证方法：** 上传一个 `.md` 文件，看它是不是按 `##` 标题切成了正确的块数。

---

---

## 生产就绪度评估 🏭

> 截至 Phase 3 结束，核心功能完成了 ~80%，工程健壮性约 20%~30%。
> 剩下的工作解决的是"这玩意儿能不能稳定跑、别人能不能接手、改完会不会炸"。

### 差距清单

| 维度 | 现状 | 优先级 |
|------|------|--------|
| **单元测试** | ❌ 一行没有，`tests/` 下只有评测数据 | 🔥 最高 |
| **错误处理** | ❌ 裸奔，文件缺失/模型加载失败直接崩 | 🔥 最高 |
| **增量更新** | ❌ 每次启动全量重建，加一个文件重算所有 | 🔥 高 |
| **结构化日志** | ❌ `print()` 走天下 | ✅ 低（半天能搞定） |
| **配置分层** | ⚠️ 有 `config.py`，但路径硬编码多 | ✅ 低 |
| **文档格式支持** | ⚠️ 基本只有 `.txt`，`.pdf` 没真正处理 | 看需求 |
| **异步/并发** | ❌ Gradio UI 同步阻塞 | 看需求 |
| **API 层** | ❌ 只有 UI，没有 FastAPI | 看需求 |
| **用户反馈闭环** | ❌ 无 | 看需求 |
| **监控/可观测性** | ❌ 无 | 看需求 |

### 建议推进顺序

1. 🔥 **pytest 单元测试** — retrieval、embedding、evaluation 各写几组
2. 🔥 **错误处理 + 边界情况** — 文件缺失、模型加载失败、空结果
3. 🔥 **增量更新** — MD5 比对，只更新变了的文件
4. ✅ **loguru 日志** — 半天切上去
5. 剩下的按需求补齐

## 学习路线建议

```
Phase 1 ──────────────────────────────────────────
  把 rag_app.py 的代码搬到 rag_forge/ 各模块里
  ⬇ 理解：模块化拆分的意义

Phase 2 ──────────────────────────────────────────
  加 Rerank，效果明显提升
  ⬇ 理解：为什么 RAG 需要 Rerank

Phase 3 ──────────────────────────────────────────
  建评测集，对比加 Rerank 前后的分数
  ⬇ 理解：没有数据就没有优化

Phase 4 ──────────────────────────────────────────
  增量更新、日志、测试
  ⬇ 理解：让系统真正能用、可维护
```

**怎么用这份计划：**
1. 打开 `rag_app.py` 放在屏幕左边
2. 打开 `rag_forge/` 对应的文件放在右边
3. 照着 Plan 的步骤，把旧代码复制过来，改参数名，跑验证
4. 卡住了就对比两个文件，想清楚为什么这么改

出了什么问题随时问我。

---
---

## Phase 5：FastAPI 后端 🚀

目标：把 `rag_forge/` 的核心能力包成 HTTP 接口，这样任何客户端（前端、移动端、第三方）都能调用。

```
rag-project/
├── backend/                 # ← 新建
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── schemas.py           # 请求/响应数据模型
│   └── router.py            # API 路由
└── rag_forge/               # 核心库，不动
```

### Step 1 — 安装 FastAPI

```bash
pip install fastapi uvicorn
```

**验证：**
```bash
python -c "import fastapi; print(fastapi.__version__)"
```

### Step 2 — 创建 backend/schemas.py

定义 API 的数据结构（Pydantic 模型），用类型注解自动校验参数：

```python
from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    question: str
    history: Optional[List[dict]] = []


class SourceItem(BaseModel):
    filename: str
    score: float
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


class UploadResponse(BaseModel):
    success: bool
    message: str
    total_docs: int


class DeleteRequest(BaseModel):
    filename: str


class DeleteResponse(BaseModel):
    success: bool
    message: str
```

**你的任务：** 原样复制过去就行，这是固定结构。

### Step 3 — 创建 backend/router.py

写 API 路由，核心就是调 `rag_forge` 的函数：

```python
from fastapi import APIRouter, HTTPException
from backend.schemas import ChatRequest, ChatResponse, SourceItem
from rag_forge.retrieval.hybrid import hybrid_search

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """问答接口：接收问题，返回回答和来源"""
    try:
        # 1. 检索
        results = hybrid_search(
            request.question,
            vectordb,       # ← 启动时注入
            all_chunks,     # ← 启动时注入
            reranker=reranker,
        )
        # 2. 格式化来源
        sources = [
            SourceItem(filename=s, score=score, content=c[:200])
            for c, score, s in results
        ]
        # 3. 调 LLM 生成回答
        answer = llm.invoke(f"问题：{request.question}\n\n文档：{results[0][0]}")
        return ChatResponse(answer=answer.content, sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
def list_documents():
    """列出所有文档"""
    from rag_forge.data.manifest import sync_manifest
    from rag_forge.config import settings
    manifest = sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)
    return {"documents": [m.document for m in manifest]}


@router.post("/documents")
def add_document():
    """上传文档（文件通过 multipart 上传）"""
    # 待实现
    return {"message": "待实现"}


@router.get("/health")
def health():
    """健康检查"""
    return {"status": "ok", "reranker": reranker is not None}
```

> **注意：** `vectordb`、`all_chunks`、`reranker`、`llm` 这些变量在 router.py 里还拿不到。需要 Step 4 处理。

### Step 4 — 创建 backend/main.py

主入口：初始化 RAG 组件，注入到 router，启动服务：

```python
import sys
import os

# 确保能搜到 rag_forge
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.router import router

# 1. 初始化 RAG 组件（这块跟 app.py 差不多）
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore
from rag_forge.data.manifest import sync_manifest
from rag_forge.retrieval.reranker import Reranker

app = FastAPI(title="RAG-Forge API", version="1.0.0")

# 2. 跨域（让前端能调）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 开发阶段允许所有来源
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. RAG 全局变量
vectordb = None
all_chunks = None
reranker = None


@app.on_event("startup")
def startup():
    """启动时加载模型和构建向量库"""
    global vectordb, all_chunks, reranker

    sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)

    embeddings = create_embeddings()
    source = FileSource(settings.DATA_DIR)
    vectordb, all_chunks = build_vectorstore(source, embeddings, settings.CHROMA_DIR)
    print(f"向量库加载完成，共 {len(all_chunks)} 个块")

    if settings.RERANK_ENABLED:
        try:
            reranker = Reranker()
            print("Reranker 加载完成")
        except Exception as e:
            print(f"Reranker 加载失败，跳过：{e}")

    # 把全局变量注入到 router 模块
    import backend.router as r
    r.vectordb = vectordb
    r.all_chunks = all_chunks
    r.reranker = reranker


# 4. 注册路由
app.include_router(router)
```

**验证：**
```bash
cd d:/rag-project
python -m uvicorn backend.main:app --reload --port 8000
```

浏览器打开 `http://localhost:8000/docs`，你会看到 Swagger 交互式文档页面——这是 FastAPI 自动生成的，可以在这里直接测试接口。

### Step 5 — 实现文件上传接口

在 `backend/router.py` 加一个上传端点：

```python
from fastapi import UploadFile, File
import shutil


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传文档文件"""
    try:
        # 1. 保存文件到 data/
        file_path = os.path.join(settings.DATA_DIR, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 2. 重建向量库
        embeddings = create_embeddings()
        source = FileSource(settings.DATA_DIR)
        vectordb, all_chunks = build_vectorstore(source, embeddings, settings.CHROMA_DIR)

        # 3. 更新 router 里的全局变量
        import backend.router as r
        r.vectordb = vectordb
        r.all_chunks = all_chunks

        return UploadResponse(success=True, message=f"{file.filename} 上传成功", total_docs=len(all_chunks))
    except Exception as e:
        return UploadResponse(success=False, message=str(e), total_docs=0)
```

✅ **Phase 5 完成标志：**
```bash
curl http://localhost:8000/health
# 返回 {"status": "ok", "reranker": false}
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是跨域"}'
# 返回回答 + 来源
```

---

## Phase 6：Vue3 前端 🎨

目标：一个极简的聊天界面 + 文档管理页面，调 Phase 5 的 API。

```
rag-project/
├── frontend/                 # ← 新建
│   ├── index.html            # 入口
│   ├── package.json
│   ├── vite.config.js
│   ├── App.vue               # 主组件（选项卡切换）
│   ├── api.js                # 封装 API 调用
│   ├── ChatView.vue          # 聊天页面
│   └── DocManager.vue        # 文档管理页面
└── backend/                  # 上面建的后端
```

### Step 1 — 初始化 Vue3 + Vite 项目

```bash
cd d:/rag-project
npm create vite@latest frontend -- --template vue
cd frontend
npm install
```

这会生成 `frontend/` 的基本架子，然后安装依赖。

### Step 2 — 创建 api.js

封装所有后端调用，一个文件搞定：

```javascript
// frontend/src/api.js
const BASE = "http://localhost:8000"

export async function chat(question, history = []) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  })
  return res.json()
}

export async function getDocuments() {
  const res = await fetch(`${BASE}/documents`)
  return res.json()
}

export async function uploadDocument(file) {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form })
  return res.json()
}

export async function healthCheck() {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}
```

### Step 3 — 创建 ChatView.vue

聊天界面，核心逻辑：

```vue
<template>
  <div class="chat-container">
    <div class="messages">
      <div v-for="(msg, i) in messages" :key="i" :class="msg.role">
        <strong>{{ msg.role === 'user' ? '你' : 'AI' }}：</strong>
        <span>{{ msg.content }}</span>
        <div v-if="msg.sources" class="sources">
          <small v-for="s in msg.sources" :key="s.filename">
            📄 {{ s.filename }} ({{ (s.score * 100).toFixed(0) }}%)
          </small>
        </div>
      </div>
    </div>
    <div class="input-row">
      <input v-model="question" @keyup.enter="send" placeholder="输入问题..." />
      <button @click="send" :disabled="loading">{{ loading ? '思考中...' : '发送' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { chat } from './api.js'

const question = ref('')
const messages = ref([])
const loading = ref(false)

async function send() {
  if (!question.value.trim()) return
  const q = question.value
  messages.value.push({ role: 'user', content: q })
  question.value = ''
  loading.value = true

  try {
    const res = await chat(q, messages.value)
    messages.value.push({
      role: 'assistant',
      content: res.answer,
      sources: res.sources || [],
    })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '请求失败：' + e.message })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.chat-container { max-width: 800px; margin: auto; padding: 20px; }
.messages { height: 500px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 8px; }
.messages .user { text-align: right; }
.messages .assistant { text-align: left; }
.input-row { display: flex; gap: 10px; margin-top: 10px; }
.input-row input { flex: 1; padding: 10px; font-size: 16px; }
.sources { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
</style>
```

### Step 4 — 创建 DocManager.vue

文档管理页面：

```vue
<template>
  <div class="doc-manager">
    <h3>📁 文档管理</h3>

    <div class="upload-area">
      <input type="file" @change="upload" accept=".txt,.pdf,.docx,.md" />
      <button @click="$refs.fileInput.click()">选择文件</button>
    </div>

    <div v-if="uploading">上传中...</div>

    <div class="doc-list">
      <div v-for="doc in docs" :key="doc" class="doc-item">
        📄 {{ doc }}
      </div>
      <div v-if="docs.length === 0">暂无文档</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDocuments, uploadDocument } from './api.js'

const docs = ref([])
const uploading = ref(false)

onMounted(async () => {
  const res = await getDocuments()
  docs.value = res.documents || []
})

async function upload(event) {
  const file = event.target.files[0]
  if (!file) return
  uploading.value = true
  await uploadDocument(file)
  uploading.value = false
  // 刷新列表
  const res = await getDocuments()
  docs.value = res.documents || []
}
</script>
```

### Step 5 — 组装 App.vue

左右切换两个视图：

```vue
<template>
  <div id="app">
    <h1>📚 RAG 知识库问答</h1>
    <div class="tabs">
      <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">💬 问答</button>
      <button :class="{ active: tab === 'docs' }" @click="tab = 'docs'">📁 文档管理</button>
    </div>
    <ChatView v-if="tab === 'chat'" />
    <DocManager v-if="tab === 'docs'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ChatView from './ChatView.vue'
import DocManager from './DocManager.vue'

const tab = ref('chat')
</script>

<style>
body { font-family: sans-serif; margin: 0; padding: 20px; }
.tabs { display: flex; gap: 10px; margin-bottom: 20px; }
.tabs button { padding: 10px 20px; border: 1px solid #ccc; background: #f5f5f5; cursor: pointer; }
.tabs .active { background: #4a90d9; color: white; }
</style>
```

### Step 6 — 启动

开两个终端：

```bash
# 终端 1：后端
cd d:/rag-project
uvicorn backend.main:app --reload --port 8000

# 终端 2：前端
cd d:/rag-project/frontend
npm run dev
```

浏览器打开前端地址（默认 `http://localhost:5173`），就可以问答了。

✅ **Phase 6 完成标志：**
- 前端页面能正常显示
- 发消息能收到 AI 回答
- 文档管理能列出文件、上传新文件

---

## 三种模式切换指南

项目做到这就有了三个入口，按需选用：

| 入口 | 启动命令 | 适合场景 |
|------|----------|----------|
| `rag_app.py` | `python rag_app.py` | 怀旧 / 对比新旧区别 |
| `rag_forge/ui/app.py` | `python -m rag_forge.ui.app` | 日常自用，开箱即用 |
| `backend/main.py` + `frontend/` | `uvicorn` + `npm run dev` | 展示全栈能力 / 给其他人用 |

核心都在 `rag_forge/` 里，不管用哪个入口，检索逻辑和文档数据是同一份，不用维护三套。
