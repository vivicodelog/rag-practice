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

### 4.1 增量更新

思路：
1. 每个文件存 MD5 到 sync_state
2. 只对新文件和 MD5 变化的文件重新索引
3. 从 Chroma 按 `doc_id` 删除旧块
4. 只添加新块

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

在 `tests/` 目录下写 pytest 测试：
- `test_vector.py` — 向量检索返回格式正确
- `test_keyword.py` — 关键词能找到确定匹配
- `test_hybrid.py` — 混合检索不返回空
- `test_reranker.py` — Rerank 后分数比之前高

### 4.4 文档类型自适应切分

| 类型 | 切分器 | 参数 |
|------|--------|------|
| TXT | RecursiveCharacterTextSplitter | 300/30 |
| PDF | RecursiveCharacterTextSplitter | 按页分段 |
| MD | MarkdownHeaderTextSplitter | 按 ## 标题 |
| DOCX | RecursiveCharacterTextSplitter | 500/50 |
| 代码 | RecursiveCharacterTextSplitter | 按函数切分 |

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
