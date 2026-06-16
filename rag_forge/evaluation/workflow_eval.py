"""
Workflow 回答质量评测

对比三种模式：单 Agent / Workflow(无Reviewer) / Workflow(有Reviewer)
指标：LLM-as-Judge 打分（1-5）
"""
import json
import os

from rag_forge.agent.agent import create_llm, build_agent,tools 
from rag_forge.agent.tools import review_result, search_docs
from rag_forge.config import settings
from backend.workflow import Workflow, WorkflowNode


def load_questions(path: str = None) -> list[dict]:
    """加载评测问题集，复用 tests/eval_dataset.json"""
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "tests", "eval_dataset.json",
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [{"id": item["id"], "question": item["question"]} for item in data]


def setup_single_agent():
    """
    初始化单 Agent 模式。
    """
    llm = create_llm(
        api_key=settings.DEEPSEEK_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )
    system_prompt = open(
        os.path.join(settings.PROMPTS_DIR, "system.md"),
        encoding="utf-8",
    ).read().strip()
    agent = build_agent(llm, tools, system_prompt=system_prompt)
    return agent


def setup_workflow(use_reviewer: bool = True):
    """
    初始化 Workflow 模式。

    use_reviewer=True  → Researcher → Writer → Reviewer
    use_reviewer=False → Researcher → Writer
    """
    # ── 第1步：加载 prompts ──
    # researcher.md → 读成字符串
    # writer.md     → 读成字符串
    # reviewer.md   → 如果要的话
    researcher_prompt = open(
        os.path.join(settings.PROMPTS_DIR_AGENT, "researcher.md"),
        encoding="utf-8",
    ).read().strip()
    writer_prompt = open(
        os.path.join(settings.PROMPTS_DIR_AGENT, "writer.md"),
        encoding="utf-8",
    ).read().strip()
    reviewer_prompt = open(
        os.path.join(settings.PROMPTS_DIR_AGENT, "reviewer.md"),
        encoding="utf-8",
    ).read().strip() if use_reviewer else ''
    # ── 第2步：定义工具列表 ──
    # Researcher 需要 search_docs
    # Reviewer 需要 review_result 工具
    # Writer 不需要工具
    # tools = [search_docs,review_result] 
    # ── 第3步：组装节点列表 ──
    # 先建 researcher_node
    # 再建 writer_node
    # 如果要 reviewer，再建 reviewer_node（output_type="tool"）
    researcher_node = WorkflowNode(
        role="researcher",
        tools=[search_docs],
        prompt=researcher_prompt,
        output_key="answer",
        output_type="text"
    )
    writer_node = WorkflowNode(
        role="writer",
        tools=[],
        prompt=writer_prompt,
        output_key="answer",
        output_type="text"
    )
    reviewer_node = WorkflowNode(
        role="reviewer",
        tools=[review_result],
        prompt=reviewer_prompt,
        output_key="review_verdict",
        output_type="tool"
    )if use_reviewer else None
    # ── 第4步：创建 Workflow 实例 ──
    # Workflow(nodes=[...], llm=...)
    llm = create_llm(
        api_key=settings.DEEPSEEK_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )
    return Workflow(
       nodes = [n for n in [researcher_node, writer_node, reviewer_node] if n is not None],
        llm = llm,
    )


def run_eval_question(question: str, agent, workflow_no_reviewer, workflow_with_reviewer):
    """
    对一道题跑三个模式，返回各自的答案。

    返回值格式：
    {
        "single_agent": "答案文本",
        "workflow_no_reviewer": "答案文本",
        "workflow_with_reviewer": "答案文本",
    }
    """
    # ── 单 Agent ──
    # agent.invoke() 返回 {"messages": [HumanMessage, AIMessage...]}
    # 从最后一条消息取 .content 就能拿到纯文本
    answer_single = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )["messages"][-1].content
    # ── Workflow 无 Reviewer ──
    # workflow_no_reviewer.run(question) → {"answer": "...", "steps": [...]}
    answer_no_reviewer = workflow_no_reviewer.run(question).get("answer")
    # ── Workflow 有 Reviewer ──
    # workflow_with_reviewer.run(question) → 同上
    answer_reviewer = workflow_with_reviewer.run(question).get("answer")
    return {
        "single_agent": answer_single,
        "workflow_no_reviewer": answer_no_reviewer,
        "workflow_with_reviewer": answer_reviewer,
    }


def llm_judge_score(question: str, answer: str, judge_llm) -> dict:
    """
    让 LLM 裁判给答案打分。

    打分维度（每个 1-5）：
      - accuracy:   答案是否基于事实，有没有编造
      - source_hit: 是否标注了信息来源
      - completeness: 是否完整回答了问题

    返回：
    {"accuracy": 4, "source_hit": 3, "completeness": 5}
    """
    # ── 第1步：构造打分 prompt ──
    # 用 f-string 把 question 和 answer 嵌入
    # 要求返回 JSON 格式：{"accuracy": 分, "source_hit": 分, "completeness": 分}

    # Python：f-string（f 前缀 + {}）
    user_msg = f"用户的问题是：{question}，答案是：{answer}"   
    prompt = f"""
    请对以下答案进行打分。
    打分维度（每个 1-5）：
    - accuracy:   1=大量编造  3=基本正确  5=完全基于事实
    - source_hit: 1=无来源    3=部分标注  5=所有信息都标了来源
    - completeness: 1=答非所问 3=基本覆盖  5=完整全面

    要求返回 JSON 格式，不需要任何文字解释：{{"accuracy": 分, "source_hit": 分, "completeness": 分}}
    """
    # ── 第2步：调 LLM ──
    # judge_llm.invoke(prompt) → 从 content 里提取 JSON
    response = judge_llm.invoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_msg},
    ])
    # ── 第3步：解析并返回 ──
    # 用 json.loads() 解析，失败则返回默认分（全 3 分）
    try:
        return json.loads(response.content)
    except:
        return {
            "accuracy": 3,
            "source_hit": 3,
            "completeness": 3,
        }


def print_comparison(all_scores: list[dict]):
    """
    打印三种模式的对比表格。
    """
    # ── 第1步：按模式汇总，算平均值 ──
    # modes = ["single_agent", "workflow_no_reviewer", "workflow_with_reviewer"]
    # dims = ["accuracy", "source_hit", "completeness"]
    # 两层循环取平均
    # 外层：循环三种模式
    #   内层：循环三个维度
    #       把该模式该维度的所有分数加起来 ÷ 总题数
    modes = ["single_agent", "workflow_no_reviewer", "workflow_with_reviewer"]
    dims = ["accuracy", "source_hit", "completeness"]

    averages = {}  # → {"single_agent": {"accuracy": 3.8, ...}, ...}

    for mode in modes:
        averages[mode] = {}
        for dim in dims:
            # 遍历 all_scores，取出每条数据里 当前mode.当前dim 的分数
            # 求平均，存到 averages[mode][dim]
            total = sum(item[mode][dim] for item in all_scores)
            avg = total / len(all_scores)
            averages[mode][dim] = avg

    # ── 第2步：打印表格 ──
    # 参考 AI_ASSISTANT_PLAN.md 的表格格式
    # 模式的中文名，打印用
    mode_names = {
        "single_agent": "单 Agent",
        "workflow_no_reviewer": "Workflow(无Reviewer)",
        "workflow_with_reviewer": "Workflow(有Reviewer)",
    }
    dim_names = ["accuracy", "source_hit", "completeness"]
    dim_labels = ["准确率", "来源命中率", "回答完整度"]

    # ── 第2步：打印表头 ──
    # 用 print(f"| ... ") 打第一行，字段用 | 隔开
    # 提示：模式字段占 14 格，数字字段占 9 格居中
    val_str = "| {:<16} | {:>11} | {:>11} | {:>9} |"
    print(val_str.format("模式", *dim_labels))
    # ── 第3步：打印分隔行 ──
    # 每个字段对应的 --- 数量要匹配宽度
    # print(f"|{'---':->14}|{'---':->9}|...")
    print("|" + "-" * 16 + "|" + "-" * 11 + "|" + "-" * 11 + "|" + "-" * 11 + "|")


    # ── 第4步：打印数据行 ──
    # 遍历 modes，从 averages 里取值
    # 用 f"{averages[mode][dim]:.1f}" 控制小数位数
    # 示例：print(f"| {mode_names[mode]:<14}| {avg_accuracy:>8.1f} | ...")
    for mode in modes:
        avg_accuracy = f"{averages[mode]['accuracy']:.1f}"
        avg_source_hit = f"{averages[mode]['source_hit']:.1f}"
        avg_completeness = f"{averages[mode]['completeness']:.1f}"
        print(val_str.format(mode_names[mode], avg_accuracy, avg_source_hit, avg_completeness))


def main():
    """
    主流程：加载问题 → 初始化三种模式 → 逐题跑 → LLM打分 → 打印对比
    """
    questions = load_questions()
    
    # 初始化三种模式
    agent = setup_single_agent()
    workflow_no_reviewer = setup_workflow(use_reviewer=False)
    workflow_with_reviewer = setup_workflow(use_reviewer=True)
    
    # 再创建一个 LLM 专门当裁判
    judge_llm = create_llm(
        api_key=settings.DEEPSEEK_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )
    # 逐题跑
    all_results = []
    for q in questions:
        result = run_eval_question(q["question"], agent, workflow_no_reviewer, workflow_with_reviewer)
        
        all_results.append({
            "qid": q["id"],
            "question": q["question"],
            "single_agent": llm_judge_score(q["question"], result["single_agent"], judge_llm),
            "workflow_no_reviewer": llm_judge_score(q["question"], result["workflow_no_reviewer"], judge_llm),
            "workflow_with_reviewer": llm_judge_score(q["question"], result["workflow_with_reviewer"], judge_llm),
        })

    
    # 打表
    print_comparison(all_results)


if __name__ == "__main__":
    main()
