# 🤖 多 Agent 系统构建计划

> 在现有单 Agent（`bind_tools`）基础上，构建多 Agent 协作系统。
> 核心逻辑在 `rag_forge/agent/` 里分层，不影响现有功能。

---

## 整体架构

```
用户提问
  │
  ▼
┌──────────────────────────────────────────────┐
│              Orchestrator（协调器）            │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ 拆解问题   │→│ 派发任务   │→│ 汇总结果     │ │
│  └──────────┘  └──────────┘  └────────────┘ │
└────────────┬─────────────────────────────────┘
             │
      ┌──────┴──────┐
      ▼              ▼
┌──────────┐   ┌──────────┐
│Researcher │   │  Writer  │
│ 研究员     │   │ 写作者    │
├──────────┤   ├──────────┤
│搜文档      │   │组织语言    │
│分析提炼    │   │格式化输出  │
└──────────┘   └──────────┘
      │              │
      └──────┬──────┘
             ▼
      ┌──────────┐
      │ Reviewer │  ← 第二轮加入
      │ 审查员    │
      └──────────┘
```

---

## 新增文件结构

```
rag_forge/agent/
├── agent.py              ← 不动，旧单 Agent
├── tools.py              ← 不动，工具复用
├── multi_agent.py        ← 新建：Orchestrator + Researcher + Writer
└── prompts/
    ├── researcher.md     ← 新建：研究员系统提示词
    └── writer.md         ← 新建：写作者系统提示词
```

```
backend/
├── router.py             ← 新增 /chat/multi 接口
```

---

## Round 1：Researcher → Writer 串行（2-3 天）

目标：两个 Agent 接力跑，跑通全流程。

### Step 1 — 创建研究员系统提示词

`rag_forge/agent/prompts/researcher.md`

角色定位：你是一个研究员，负责搜索知识库，提炼关键信息。

**必须做到：**
- 调用 `search_docs` 搜索用户的查询
- 把搜索结果整理成结构化的研究发现（摘要 + 要点）
- 如果没搜到相关信息，如实说明

**禁止：**
- 不要自己编答案
- 不要做总结之外的加工

### Step 2 — 创建写作者系统提示词

`rag_forge/agent/prompts/writer.md`

角色定位：你是一个写作者，负责把研究发现组织成好读的答案。

**必须做到：**
- 基于研究员提供的信息来写
- 标注信息来源（文件名）
- 用 Markdown 格式输出，清晰分段

**禁止：**
- 不要添加研究员没有提供的信息
- 不要隐藏"没找到"的事实

### Step 3 — 实现 multi_agent.py

核心逻辑：

```python
class MultiAgent:
    """多 Agent 协作入口"""

    def __init__(self, llm):
        self.llm = llm
        self.researcher = self._build_researcher()
        self.writer = self._build_writer()

    def chat(self, question: str) -> dict:
        # 1. 研究员干活（调 search_docs → 提炼）
        research_result = self.researcher.invoke(question)
        # 2. 写作者干活（基于研究结果写答案）
        final_answer = self.writer.invoke(question, research_result)
        # 3. 返回答案 + 来源
        return {"answer": final_answer, "sources": [...]}
```

**关键设计：**
- 两个 Agent 都用 `bind_tools`，但工具集不同
  - Researcher 有 `search_docs`（搜知识库）
  - Writer 没有任何工具（只负责写）
- Researcher 的输出（研究发现）通过 `SystemMessage` 或 `HumanMessage` 传给 Writer
- 来源（sources）在 Researcher 调用 `search_docs` 时顺手攒

### Step 4 — 在 router.py 加新接口

```python
@router.post("/chat/multi", response_model=ChatResponse)
def multi_chat(request: ChatRequest):
    """多 Agent 协作接口"""
    ...
```

### ✅ Round 1 完成标志

```bash
curl -X POST http://localhost:8000/chat/multi \
  -H "Content-Type: application/json" \
  -d '{"question": "Python 怎么读文件"}'
# 返回的答案经过"研究 → 写作"两步，结构更清晰
```

---

## Round 2：加 Reviewer 审查（1-2 天）

目标：Writer 写完后 Reviewer 检查质量，不合格打回重写。

### Step 1 — 创建审查员系统提示词

`rag_forge/agent/prompts/reviewer.md`

**审查维度：**
1. 答案是否基于研究员提供的信息？
2. 信息来源是否标注？
3. 有没有编造的内容？
4. 是否回答了用户的问题？

**输出格式：**
```
通过 / 不通过
理由：...
修改建议：...
```

### Step 2 — 修改多 Agent 流程

```
Researcher → Writer → Reviewer
                        │
            通过 ←──────┴──────→ 不通过 → Writer 重写 → 再审查
                                                      │
                                             最多重写 2 次
```

### Step 3 — 加一个回显日志

把每个 Agent 的 "思考过程" 记到日志里：

```
[Researcher] 收到问题：Python 怎么读文件
[Researcher] 调用 search_docs("Python 文件读取")
[Researcher] 找到 3 篇相关文档
[Researcher] 提炼完成，交给 Writer

[Writer] 收到研究发现
[Writer] 组织答案中...

[Reviewer] 审查中...
[Reviewer] 通过
```

### ✅ Round 2 完成标志

写一个测试问题（比如故意让 Researcher 搜不到），看 Reviewer 能不能正确识别并让 Writer 重写。

---

## Round 3：评测对比（1-2 天）

目标：用数据证明多 Agent 比单 Agent 好。

### Step 1 — 复用已有评测集

用之前 `tests/eval_dataset.json` 的评测题。

### Step 2 — 跑对比

| 模式 | 准确率 | 来源命中率 | 回答结构评分 |
|------|--------|-----------|------------|
| 单 Agent | ? | ? | ? |
| 多 Agent（无 Reviewer） | ? | ? | ? |
| 多 Agent（有 Reviewer） | ? | ? | ? |

评测维度：
- **准确率**：答案是否正确（LLM-as-Judge 打分）
- **来源命中率**：答案是否引用了正确的文档
- **结构评分**：答案是否结构清晰（分段、标注来源）

### ✅ Round 3 完成标志

有一张对比表格，能看到 Reviewer 带来的提升。

---

## Round 4：前端展示思考链（2-3 天）

目标：Vue 前端实时展示多 Agent 的思考过程。

### Step 1 — 后端加 SSE 或 WebSocket

把每个 Agent 的执行过程实时推送给前端：

```
事件类型：
  agent_start    → {role: "researcher", input: "..."}
  agent_action   → {role: "researcher", action: "search_docs", query: "..."}
  agent_result   → {role: "researcher", output: "..."}
  agent_end      → {role: "researcher"}
```

### Step 2 — 前端展示

```
┌─────────────────────────────────────┐
│  💬 问答                          │
├─────────────────────────────────────┤
│  你：Python 怎么读文件              │
│                                     │
│  🔍 研究员正在搜索...              │
│    → 搜索"Python 文件读取"          │
│    → 找到 3 篇文档                  │
│    → 提炼完成                      │
│                                     │
│  ✍️ 写作者正在组织答案...           │
│    → 完成                          │
│                                     │
│  ✅ 审查员检查质量                  │
│    → 通过                          │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ Python 读取文件的方法...     │   │
│  │ 📄 python_basics.txt (85%)   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### ✅ Round 4 完成标志

刷新页面，发一个问题，能看到 Agent 一步步执行的动画效果。

---

## 学习重点

| 概念 | 出现位置 | 说明 |
|------|---------|------|
| 角色隔离 | 每个 Agent 独立 system prompt | Researcher 只有搜的权限，Writer 只有写的权限 |
| 工具权限控制 | Researcher 拿 search_docs，Writer 不拿任何工具 | 比单 Agent 更精细的权限控制 |
| 结果校验 | Reviewer 环节 | 让 LLM 自己检查自己 |
| 多轮交互 | Reviewer 不通过 → Writer 重写 | Agent 之间的对话 |
| SSE/WebSocket | 前端实时展示 | Agent 可观测性 |
| LLM-as-Judge | 评测环节 | 用 LLM 打分代替人肉评估 |

---

## 怎么用这份计划

1. 每轮做完再开始下一轮
2. 卡住了问我，我给思路
3. 需要我写代码的时候，说一声就行
