# 🧠 AI 问答助手 — 构建计划

> 在现有单 Agent 基础上，构建 Workflow 编排能力。
> 核心技术：RAG + Agent + Workflow，这些是**焊在身上的技能，不会因为行业热词变化而贬值**。
> 
> 前端是你的基本盘，够用就行，不是核心卖点。

---

## 定位

**这个项目的核心价值：**
- Workflow 编排 —— 多角色有序协作，你自己设计的轻量级框架
- 评测数据 —— 单 Agent vs Workflow vs 有 Reviewer 的对比，用数据说话
- 工程完整 —— 从后端到前端，能跑能演示

---

## 整体架构

```
用户提问
  │
  ▼
┌─────────────────────────────────────┐
│        后端 Workflow 编排            │
│  ┌──────────┐  ┌──────────┐        │
│  │Researcher│→│  Writer   │        │
│  │ 搜+提炼   │  │ 组织答案  │        │
│  └──────────┘  └──────────┘        │
│       │              │              │
│       └──────┬───────┘              │
│              ▼                      │
│       ┌──────────┐                 │
│       │ Reviewer │  ← 检查质量      │
│       └──────────┘                 │
└──────────────┬──────────────────────┘
               │
               ▼
        ┌──────────────┐
        │  前端展示结果  │  ← 配套，够用就行
        └──────────────┘
```

---

## 新增文件

```
Round 1-2（后端核心）：
rag_forge/agent/
├── agent.py              ← 不动
├── tools.py              ← 不动
├── workflow.py           ← 新建：Workflow 编排核心
└── prompts/
    ├── researcher.md     ← ✅ 已建
    └── writer.md         ← ✅ 已建

backend/
└── router.py             ← 新增 /chat/workflow 接口

Round 3（评测）：
tests/
└── eval_workflow.py      ← 新建：Workflow 评测脚本

Round 4（前端配套）：
frontend/src/
└── views/
    └── WorkflowChat.vue  ← 新建：带步骤展示的聊天页

backend/
└── sse.py                ← 新建：SSE 推送（Round 4 才需要）
```

---

## Round 1：后端 Workflow 核心（2-3 天）

目标：Researcher → Writer 串行跑通，后端能输出每个步骤的日志。

### Step 1 — 创建 system prompt

`rag_forge/agent/prompts/researcher.md`

研究员职责：
- 调 `search_docs` 搜索知识库
- 把搜索结果整理成结构化的研究发现（摘要 + 要点）
- 没搜到就如实说，不编

`rag_forge/agent/prompts/writer.md`

写作者职责：
- 基于研究发现组织答案
- 标注信息来源（文件名）
- Markdown 输出

### Step 2 — 实现 workflow.py

核心类设计：

```python
class WorkflowNode:
    """一个步骤"""
    role: str          # "researcher" | "writer"
    tools: list        # 绑定的工具
    prompt: str        # 系统提示词
    output_key: str    # 产出存到哪里

class Workflow:
    """编排多个步骤"""
    def __init__(self, nodes: list[WorkflowNode]):
        ...

    def run(self, question: str) -> dict:
        # 按顺序执行每个 node
        # 上一个 node 的产出传给下一个
        # 返回最终答案 + 步骤日志
```

**不复杂，就两个类。** Researcher 产出传给 Writer，就这么简单。

### Step 3 — 每个步骤输出结构化日志

每个节点执行时，记录这些字段：

```python
{
    "role": "researcher",
    "status": "running" | "done",
    "input": "用户问题",
    "actions": ["调用了 search_docs(query=...)"],
    "output": "研究发现摘要",
}
```

这些日志就是后续推送给前端的素材。

### Step 4 — 在 router.py 加接口

```python
@router.post("/chat/workflow")
def chat_workflow(request: ChatRequest):
    """Workflow 模式问答"""
```

✅ **Round 1 完成标志：** `curl` 调接口能在日志里看到 Researcher 和 Writer 的执行步骤。

---

## Round 2：加 Reviewer 审查（1-2 天）

目标：Writer 写完，Reviewer 检查，不合格重写。

### Step 1 — 创建审查员 prompt

`rag_forge/agent/prompts/reviewer.md`

审查维度：
1. 答案是否基于事实？
2. 来源是否标注？
3. 有没有编造内容？
4. 是否回答了用户问题？

### Step 2 — 修改 Workflow

```
Researcher → Writer → Reviewer
                        │
            通过 ←──────┴──────→ 不通过 → Writer 重写 → 再审查
                                                      │
                                             最多重写 2 次
```

✅ **Round 2 完成标志：** 故意让 Researcher 搜到不相关内容，看 Reviewer 能不能打回重写。

---

## Round 3：评测对比（1-2 天）

目标：用数据说话。

### Step 1 — 跑三组对比

| 模式 | 准确率 | 来源命中率 | 回答完整度 |
|------|--------|-----------|-----------|
| 单 Agent（现有） | ? | ? | ? |
| Workflow（无 Reviewer） | ? | ? | ? |
| Workflow（有 Reviewer） | ? | ? | ? |

### Step 2 — LLM-as-Judge 打分

让一个 LLM 给三个模式的答案打分（1-5 分），取平均值。

✅ **Round 3 完成标志：** 一张对比表格，数据能看出 Workflow 优于单 Agent，Reviewer 有额外提升。

---

## Round 4：前端展示思考链（2-3 天，优先级最低）

目标：前端能看到 Workflow 执行过程。**够用就行，不追求炫酷。**

### Step 1 — 后端加 SSE

把每个步骤的执行状态推给前端：

```python
@router.get("/chat/workflow/stream")
def stream_workflow(question: str):
    def event_stream():
        yield {"event": "node_start", "data": {"role": "researcher", ...}}
        # 执行 researcher...
        yield {"event": "node_end", "data": {"role": "researcher", "output": ...}}
        yield {"event": "node_start", "data": {"role": "writer", ...}}
        # 执行 writer...
        yield {"event": "node_end", "data": {"role": "writer", "output": ...}}
        yield {"event": "done", "data": {"answer": "...", "sources": [...]}}
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Step 2 — 前端简单展示

```
┌──────────────────────────────────┐
│ 🔍 研究员 — 完成                 │
│ ✍️ 写作者 — 完成                 │
│ ✅ 审查员 — 通过                 │
├──────────────────────────────────┤
│ 最终答案（Markdown 渲染）        │
│ 📄 来源标签                     │
└──────────────────────────────────┘
```

✅ **Round 4 完成标志：** 能展示步骤状态和最终答案，不需要动画特效。

---

## 简历亮点汇总

做完这四轮，简历上可以写：

> **AI 知识库问答助手 | Python + Vue 3**
>
> - 设计并实现了基于 Workflow 的 AI 问答系统，支持 Researcher / Writer / Reviewer 多角色协作
> - 通过 SSE 实时推送 Agent 思考过程，前端可视化展示内部推理链路
> - 构建评测体系，定量对比单 Agent / Workflow / Workflow+Reviewer 三种模式的准确率和完整性
> - 独立完成从后端编排到前端展示的全栈开发

---

## 怎么用这份计划

1. 四轮顺序做，每轮做完了再开始下一轮
2. 卡住了问我，我给思路
3. 需要我写代码的时候，说一声就行
