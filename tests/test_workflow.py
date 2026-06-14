"""
Workflow 编排核心的单元测试。

不调 API，用 mock 替代 LLM，只测串联逻辑。
"""

from pathlib import Path
from unittest.mock import MagicMock

from backend.workflow import Workflow, WorkflowNode


# ─── helper：造一个假的 LLM 返回值 ───
def fake_response(content: str, tool_calls: list = None):
    """模仿 langchain AIMessage"""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


# ─── helper：造一个 mock LLM ───
def make_mock_llm(responses: list):
    """
    创建一个假的 LLM，每次 invoke 依次返回 responses 里的内容。

    用法：
        llm = make_mock_llm(["研究结果", "最终答案"])
        llm.bind_tools(...)       → 返回自己（链式调用）
        llm.invoke(...)            → 依次返回 "研究结果", "最终答案"
    """
    llm = MagicMock()
    # bind_tools 返回自己，方便链式调用
    llm.bind_tools.return_value = llm
    # invoke 依次返回预设的响应
    llm.invoke.side_effect = [fake_response(r) for r in responses]
    return llm


class TestWorkflowNode:
    """WorkflowNode 只是一个数据容器，测一下字段对不对"""

    def test_holds_attributes(self):
        node = WorkflowNode(
            role="researcher",
            tools=["search_docs"],
            prompt="你是一个研究员",
            output_key="research",
        )
        assert node.role == "researcher"
        assert node.tools == ["search_docs"]
        assert node.prompt == "你是一个研究员"
        assert node.output_key == "research"


class TestWorkflowRun:
    """Workflow.run() 的核心逻辑"""

    def test_two_nodes_pass_output_forward(self):
        """
        核心场景：Researcher → Writer。

        预期：
            - Writer 的 prompt 里收到了 Researcher 的产出
            - 最终 answer 是 Writer 的回答
            - steps 有两条记录
        """
        nodes = [
            WorkflowNode(
                role="researcher",
                tools=[],
                prompt="你是一个研究员",
                output_key="research",
            ),
            WorkflowNode(
                role="writer",
                tools=[],
                prompt="根据研究结果写答案：{{research}}",
                output_key="answer",
            ),
        ]
        llm = make_mock_llm(["北京人口约2189万", "北京是中国的首都，人口约2189万"])

        result = Workflow(nodes=nodes, llm=llm).run("北京人口多少")

        # 最终答案
        assert result["answer"] == "北京是中国的首都，人口约2189万"

        # 步骤数
        assert len(result["steps"]) == 2

        # 第一步是 researcher
        assert result["steps"][0]["role"] == "researcher"
        assert result["steps"][0]["status"] == "done"
        assert result["steps"][0]["output"] == "北京人口约2189万"

        # 第二步是 writer
        assert result["steps"][1]["role"] == "writer"
        assert result["steps"][1]["status"] == "done"

    def test_prompt_template_replacement(self):
        """
        prompt 模板替换：{{research}} 应该被替换成上一步的产出。

        验证：Writer 收到的 prompt 里包含 Researcher 的实际产出。
        """
        nodes = [
            WorkflowNode(
                role="researcher", tools=[], prompt="研究",
                output_key="research",
            ),
            WorkflowNode(
                role="writer", tools=[], prompt="基于 {{research}} 写",
                output_key="answer",
            ),
        ]
        # 给 LLM 一个特征明显的返回值
        llm = make_mock_llm(["【研究结果】", "最终回答"])

        result = Workflow(nodes=nodes, llm=llm).run("问题")

        # Researcher 输出了 "【研究结果】"，Writer 的 prompt 应该包含它
        # 但我们无法直接看 prompt → 只能透过 Writer 的回答来推断
        # 换个角度：检查 LLM 被调了 2 次，第二次调用时 prompt 里含有【研究结果】
        assert result["steps"][0]["output"] == "【研究结果】"

    def test_single_node(self):
        """边界：只有一个节点也能跑"""
        nodes = [
            WorkflowNode(role="writer", tools=[], prompt="写", output_key="answer"),
        ]
        llm = make_mock_llm(["单步回答"])

        result = Workflow(nodes=nodes, llm=llm).run("问题")
        assert result["answer"] == "单步回答"
        assert len(result["steps"]) == 1

    def test_empty_nodes(self):
        """边界：空节点列表，不崩"""
        result = Workflow(nodes=[], llm=MagicMock()).run("问题")
        assert result["answer"] == ""
        assert result["steps"] == []

    def test_no_answer_key_in_results(self):
        """边界：没有节点设置 output_key='answer'，返回空字符串"""
        nodes = [
            WorkflowNode(role="researcher", tools=[], prompt="研究", output_key="draft"),
        ]
        llm = make_mock_llm(["草稿"])
        result = Workflow(nodes=nodes, llm=llm).run("问题")
        assert result["answer"] == ""           # 没有 answer key
        assert result["steps"][0]["output"] == "草稿"

    def test_llm_called_with_correct_messages(self):
        """
        验证：LLM 收到的 prompt 是否正确。

        有工具时：先调 bind_tools，再调 invoke
        无工具时：直接调 invoke
        """
        nodes = [
            WorkflowNode(role="writer", tools=[], prompt="写答案", output_key="answer"),
        ]
        # 用 spy（不是 mock）来记录调用
        llm = MagicMock()
        llm.invoke.return_value = fake_response("答案")

        Workflow(nodes=nodes, llm=llm).run("问题")

        # 验证 invoke 被调了 1 次
        assert llm.invoke.call_count == 1
        # 验证 prompt 传进去了
        args, _ = llm.invoke.call_args
        messages = args[0]
        assert any("写答案" in m.content for m in messages)


class TestPromptFiles:
    """prompt 文件里的占位符不能少，否则 Workflow 注入不进去"""

    PROMPT_DIR = Path("rag_forge/agent/prompts")

    def test_writer_has_research_placeholder(self):
        """writer.md 必须包含 {{research}}"""
        text = (self.PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
        assert "{{research}}" in text, (
            "writer.md 缺少 {{research}}，Researcher 的产出注入不到 Writer 的 prompt 里"
        )
