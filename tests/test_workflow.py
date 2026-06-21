"""
Workflow 编排核心的单元测试。

不调 API，用 mock 替代 LLM，只测串联逻辑。
"""

from pathlib import Path
from unittest.mock import MagicMock

from rag_forge.agent.workflow import Workflow, WorkflowNode


# ─── helper：造一个假的 LLM 返回值 ───
def fake_response(content: str, tool_calls: list | None= None):
    """模仿 langchain AIMessage，支持带 tool_calls"""
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


class TestWorkflowWithReviewer:
    """含 Reviewer 的三节点串联测试（需要 mock 工具调用）"""

    def make_review_tool(self):
        """造一个假的 review_docs 工具"""
        tool = MagicMock()
        tool.name = "review_docs"
        tool.invoke.return_value = "ok"
        return tool

    def test_reviewer_passes_first_time(self):
        """
        三节点：Researcher → Writer → Reviewer，一次审查通过。

        LLM 被调 4 次：
            0. researcher（无工具）→ 文本
            1. writer（无工具）    → 文本
            2. reviewer 第一轮    → 返回 tool_call（触发审查）
            3. reviewer 第二轮    → 返回文本结论
        """
        nodes = [
            WorkflowNode("researcher", [], "研究", "research"),
            WorkflowNode("writer", [], "基于 {{research}} 写", "answer"),
            WorkflowNode(
                "reviewer",
                [self.make_review_tool()],
                "审查：{{answer}}",
                "review_result",
                output_type="tool",
            ),
        ]

        tool_call_pass = {
            "name": "review_docs",
            "args": {"passed": True, "feedback": "", "issues": []},
            "id": "call_1",
        }

        llm = MagicMock()
        llm.bind_tools.return_value = llm
        llm.invoke.side_effect = [
            fake_response("研究结果"),                           # 0. researcher
            fake_response("北京是首都"),                          # 1. writer
            fake_response("", tool_calls=[tool_call_pass]),     # 2. reviewer 调工具
            fake_response("审查通过"),                            # 3. reviewer 出结论
        ]

        result = Workflow(nodes=nodes, llm=llm).run("北京人口")

        assert result["answer"] == "北京是首都"
        assert len(result["steps"]) == 3
        assert result["steps"][2]["role"] == "reviewer"
        assert result["steps"][2]["output"] == "审查通过"

    def test_reviewer_rewrite_once(self):
        """
        Review 不通过 → 重写一次 → 再审查通过。

        LLM 被调 7 次：
            0. researcher
            1. writer
            2. reviewer 第一轮 invoke1 → tool_call（passed=false）
            3. reviewer 第一轮 invoke2 → 文本
            4. writer 重写
            5. reviewer 第二轮 invoke1 → tool_call（passed=true）
            6. reviewer 第二轮 invoke2 → 文本
        """
        nodes = [
            WorkflowNode("researcher", [], "研究", "research"),
            WorkflowNode("writer", [], "基于 {{research}} 写", "answer"),
            WorkflowNode(
                "reviewer",
                [self.make_review_tool()],
                "审查：{{answer}}\n反馈：{{review_feedback}}",
                "review_result",
                output_type="tool",
            ),
        ]

        tool_call_fail = {
            "name": "review_docs",
            "args": {"passed": False, "feedback": "缺少数据来源", "issues": ["没有引用"]},
            "id": "call_1",
        }
        tool_call_pass = {
            "name": "review_docs",
            "args": {"passed": True, "feedback": "", "issues": []},
            "id": "call_2",
        }

        llm = MagicMock()
        llm.bind_tools.return_value = llm
        llm.invoke.side_effect = [
            fake_response("研究结果"),                           # 0
            fake_response("北京是首都"),                          # 1
            fake_response("", tool_calls=[tool_call_fail]),     # 2. reviewer 第一轮：不通过
            fake_response("不通过"),                              # 3
            fake_response("北京是首都，数据来自2020年人口普查"),    # 4. writer 重写
            fake_response("", tool_calls=[tool_call_pass]),     # 5. reviewer 第二轮：通过
            fake_response("审查通过"),                            # 6
        ]

        result = Workflow(nodes=nodes, llm=llm).run("北京人口")

        assert result["answer"] == "北京是首都，数据来自2020年人口普查"
        assert len(result["steps"]) == 3
        assert result["steps"][2]["output"] == "审查通过"
        assert result["steps"][2]["rewrite_count"] == "1"

    def test_reviewer_fails_twice(self):
        """审查两次都不通过 → 重写 2 次后放弃
   
            Review 不通过 → 重写一次 → 再审查通过。

            LLM 被调 7 次：
                0. researcher
                1. writer
                2. reviewer 第一轮 invoke1 → tool_call（passed=false）
                3. reviewer 第一轮 invoke2 → 文本
                4. writer 重写
                5. reviewer 第二轮 invoke1 → tool_call（passed=false）
                6. reviewer 第二轮 invoke2 → 文本
                7. writer 重写二轮
                8. reviewer 第二轮 invoke1 → tool_call（passed=false）
                9. reviewer 第二轮 invoke2 → 文本  
           
        """
        nodes = [
            WorkflowNode("researcher", [], "研究", "research"),
            WorkflowNode("writer", [], "基于 {{research}} 写", "answer"),
            WorkflowNode(
                "reviewer",
                [self.make_review_tool()],
                "审查：{{answer}}\n反馈：{{review_feedback}}",
                "review_result",
                output_type="tool",
            ),
        ]
        
        tool_call_fail = {
            "name": "review_docs",
            "args": {"passed": False, "feedback": "缺少数据来源", "issues": ["没有引用"]},
            "id": "call_1",
        }
        tool_call_pass = {
            "name": "review_docs",
           "args": {"passed": False, "feedback": "缺少数据来源", "issues": ["没有引用"]},
            "id": "call_2",
        }
        tool_call_pass = {
            "name": "review_docs",
           "args": {"passed": False, "feedback": "数据来源错误", "issues": ["引用错误"]},
            "id": "call_3",
        }
        llm = MagicMock()
        llm.bind_tools.return_value = llm
        llm.invoke.side_effect = [
            fake_response("研究结果"),                           # 0
            fake_response("北京是首都"),                          # 1
            fake_response("", tool_calls=[tool_call_fail]),     # 2. reviewer 第一轮：不通过
            fake_response("不通过"),                              # 3
            fake_response("北京是首都，数据来自人口普查"),    # 4. writer 重写
            fake_response("", tool_calls=[tool_call_pass]),     # 5. reviewer 第二轮：不通过
            fake_response("不通过"),                         # 6
            fake_response("北京是首都，数据来自2000年人口普查"),    #7. writer 重写
            fake_response("", tool_calls=[tool_call_pass]),     # 8. reviewer 第三轮：不通过
            fake_response("审查不通过"),                            # 9
        ]

        result = Workflow(nodes=nodes, llm=llm).run("北京人口")

        assert result["answer"] == "北京是首都，数据来自2000年人口普查"
        assert len(result["steps"]) == 3
        assert result["steps"][2]["output"] == "审查未通过\n问题：引用错误"
        assert result["steps"][2]["rewrite_count"] == "2"