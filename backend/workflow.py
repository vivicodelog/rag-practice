"""
Workflow 编排核心。

Researcher → Writer（→ Reviewer）串行执行，
每一步的产出传给下一步。
"""

from typing import Any, List

from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

class WorkflowNode:
    """一个步骤"""
    def __init__(self, role: str, tools: list, prompt: str, output_key: str, output_type: str = "text"):
        self.role = role              # "researcher" | "writer" | "reviewer"
        self.tools = tools            # 绑定的工具函数列表
        self.prompt = prompt          # 系统提示词
        self.output_key = output_key  # 产出存到 results[output_key]
        self.output_type = output_type  # "text"→取LLM文本，"tool"→取工具调用结构化数据

class Workflow:
    """编排多个步骤，按顺序执行，上一步产出传给下一步"""

    def __init__(self, nodes: List[WorkflowNode], llm: Any):
        self.nodes = nodes
        self.llm = llm

    def run(self, question: str) -> dict:
        """
        执行 Workflow。

        返回：
            answer: 最终答案
            steps:  每个步骤的日志列表
        """
        results = {}   # output_key → 文本产出
        steps = []     # 步骤日志

        for node in self.nodes:
            logger.info(f"[Workflow] 开始执行: {node.role}")

            # 1. 往 prompt 里注入上一步的产出
            prompt_text = node.prompt   #键值对一起拿就需要用.item# 只要 key #for key in results: # → research, answer
                                        # 只要值  #for val in results.values():     # → 研究结果, 最终答案
            for key, val in results.items():#不需要额外写 if 判断，空字典自然就不进循环
                prompt_text = prompt_text.replace("{{" + key + "}}", val)

            step_log = {
                "role": node.role,
                "status": "running",
                "input": question,
            }

            # 2. 执行
            #    有工具 → Agent 模式（可能多次调工具）
            #    没工具 → 直接调 LLM
            if node.tools:
                result = self._run_with_tools(prompt_text, question, node.tools)
                step_log["actions"] = result["actions"]

                if node.output_type == "tool":
                    # 取结构化数据（如 Reviewer 的审查结论）
                    if not result["tool_calls_data"]:  # 没调工具 → 视为通过
                        review_data = {"passed": True, "feedback": "", "issues": []}
                    else:
                        review_data = result["tool_calls_data"][0]["args"]
                    rewrite_count = 0

                    # 不通过则重写循环（最多 2 次）
                    while not review_data["passed"] and rewrite_count < 2:
                        rewrite_count += 1
                        results["review_feedback"] = review_data.get("feedback", "")

                        # 找到 Writer 节点，重建 prompt 后重写
                        writer_node = next(
                            (n for n in self.nodes if n.role == "writer"), None
                        )# "按角色查找" 
                        #这是 Python 内置函数 next()，它的作用是从一个迭代器里取出下一个元素。
                        # 不依赖位置 — 即使以后节点顺序变了（比如插了个别的步骤），按角色找仍然正确
                        # 找不到不崩 — 第二个参数 None 保证了万一没有 writer 节点，返回 None 而不是抛 StopIteration 异常
                        if writer_node:
                            writer_prompt = writer_node.prompt
                            # 先保存 Writer 上次的答案，再恢复研究员原始结果
                            results["previous_answer"] = results.get("answer", "")
                            results["answer"] = results.get("research_data", results["answer"])
                            # 重写时追加上下文，不影响第一次写
                            writer_prompt += f"""
                                你之前写的版本：
                                {results['previous_answer']}

                                审查反馈：
                                {results['review_feedback']}

                                请根据审查反馈修改答案。"""
                            for k, v in results.items():
                                writer_prompt = writer_prompt.replace(
                                    "{{" + k + "}}", v
                                )
                            writer_output = self._run_without_tools(
                                writer_prompt, question
                            )
                            results["answer"] = writer_output

                        # 重建 Reviewer prompt 重新审查
                        reviewer_prompt = node.prompt
                        for k, v in results.items():
                            reviewer_prompt = reviewer_prompt.replace(
                                "{{" + k + "}}", v
                            )
                        result = self._run_with_tools(
                            reviewer_prompt, question, node.tools
                        )
                        if not result["tool_calls_data"]:
                            review_data = {"passed": True, "feedback": "", "issues": []}
                        else:
                            review_data = result["tool_calls_data"][0]["args"]

                    output = (
                        f"审查{'通过' if review_data['passed'] else '未通过'}"
                    )
                    if review_data.get("issues"):
                        output += f"\n问题：{'；'.join(review_data['issues'])}"
                    step_log["rewrite_count"] = str(rewrite_count)
                else:
                    output = result["output"]
            else:
                output = self._run_without_tools(prompt_text, question)

            # 3. 存结果
            results[node.output_key] = output
            # 保存研究员原始结果，重写时要用
            if node.role == "researcher":
                results["research_data"] = output
            if node.role == "writer":
                results["previous_answer"] = output
            step_log["status"] = "done"
            step_log["output"] = output
            steps.append(step_log)

            logger.info(f"[Workflow] 完成: {node.role}")

        return {
            "answer": results.get("answer", ""),#Python 字典自带的方法，get — 没有就返回默认值 ""，不报错
            "steps": steps,
        }

    def stream(self, question: str):
        """
        Generator 版 run() — 每一步执行时 yield 事件，前端实时展示。

        Yields:
            dict，含 "event" 和 "data" 两个 key
            - node_start: {"role": "researcher"}
            - node_action: {"role": "researcher", "action": "调用了 search_docs(...)"}
            - node_end:   {"role": "researcher", "output": "..."}
            - review_result: {"passed": True/False, "issues": [...], "rewrite_count": N}
            - done:       {"answer": "...", "steps": [...]}
        """
        results = {}
        steps = []

        for node in self.nodes:
            # 1. 注入上一步产出
            prompt_text = node.prompt
            for key, val in results.items():
                prompt_text = prompt_text.replace("{{" + key + "}}", val)

            step_log = {
                "role": node.role,
                "status": "running",
                "input": question,
            }
            yield {"event": "node_start", "data": {"role": node.role}}

            # 2. 执行
            if node.tools:
                result = self._run_with_tools(prompt_text, question, node.tools)
                step_log["actions"] = result.get("actions", [])

                # 把每次工具调用单独 yield 出去
                for action in step_log["actions"]:
                    yield {"event": "node_action", "data": {"role": node.role, "action": action}}

                if node.output_type == "tool":
                    # Reviewer 的逻辑：审查 → 不通过 → 重写 → 再审查
                    if not result["tool_calls_data"]:
                        review_data = {"passed": True, "feedback": "", "issues": []}
                    else:
                        review_data = result["tool_calls_data"][0]["args"]

                    rewrite_count = 0
                    while not review_data["passed"] and rewrite_count < 2:
                        rewrite_count += 1
                        yield {
                            "event": "review_result",
                            "data": {
                                "passed": False,
                                "issues": review_data.get("issues", []),
                                "rewrite_count": rewrite_count,
                            },
                        }

                        results["review_feedback"] = review_data.get("feedback", "")

                        # 找到 Writer 节点，重建 prompt 后重写
                        writer_node = next(
                            (n for n in self.nodes if n.role == "writer"), None
                        )
                        if writer_node:
                            writer_prompt = writer_node.prompt
                            results["previous_answer"] = results.get("answer", "")
                            results["answer"] = results.get("research_data", results["answer"])
                            writer_prompt += f"""
                                你之前写的版本：
                                {results['previous_answer']}

                                审查反馈：
                                {results['review_feedback']}

                                请根据审查反馈修改答案。"""
                            for k, v in results.items():
                                writer_prompt = writer_prompt.replace("{{" + k + "}}", v)
                            writer_output = self._run_without_tools(
                                writer_prompt, question
                            )
                            results["answer"] = writer_output
                            yield {
                                "event": "node_end",
                                "data": {
                                    "role": "writer",
                                    "output": writer_output,
                                    "rewrite": True,
                                },
                            }

                        # 重建 Reviewer prompt 重新审查
                        reviewer_prompt = node.prompt
                        for k, v in results.items():
                            reviewer_prompt = reviewer_prompt.replace("{{" + k + "}}", v)
                        result = self._run_with_tools(
                            reviewer_prompt, question, node.tools
                        )
                        if not result["tool_calls_data"]:
                            review_data = {"passed": True, "feedback": "", "issues": []}
                        else:
                            review_data = result["tool_calls_data"][0]["args"]

                    yield {
                        "event": "review_result",
                        "data": {
                            "passed": review_data["passed"],
                            "issues": review_data.get("issues", []),
                            "rewrite_count": rewrite_count,
                        },
                    }
                    # 重写完成后，把 Writer 状态设回 done（前端展示用）
                    if rewrite_count > 0:
                        yield {
                            "event": "node_end",
                            "data": {
                                "role": "writer",
                                "output": results.get("answer", ""),
                            },
                        }
                    output = (
                        f"审查{'通过' if review_data['passed'] else '未通过'}"
                    )
                    if review_data.get("issues"):
                        output += f"\n问题：{'；'.join(review_data['issues'])}"
                    step_log["rewrite_count"] = str(rewrite_count)
                else:
                    output = result["output"]
            else:
                output = self._run_without_tools(prompt_text, question)

            # 3. 存结果
            results[node.output_key] = output
            if node.role == "researcher":
                results["research_data"] = output
            if node.role == "writer":
                results["previous_answer"] = output
            step_log["status"] = "done"
            step_log["output"] = output
            steps.append(step_log)

            yield {"event": "node_end", "data": {"role": node.role, "output": output}}

        yield {
            "event": "done",
            "data": {
                "answer": results.get("answer", ""),
                "steps": steps,
            },
        }

    def _run_with_tools(self, prompt: str, question: str, tools: list) -> dict:
        """有工具的步骤：调 Agent，处理工具调用循环"""
        llm_with_tools = self.llm.bind_tools(tools)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=question),
        ]

        actions = []         # 记录调了哪些工具
        tool_calls_data = [] # 记录每次工具调用的参数
        tool_map = {tool.name.lower(): tool for tool in tools}

        for _ in range(3):   # 最多 3 轮工具调用
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break  # 没调工具 → 最终回答

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"].lower()
                tool_args = tool_call["args"]
                tool_calls_data.append({"name": tool_name, "args": tool_args})

                tool_fn = tool_map.get(tool_name)
                if tool_fn:
                    result = tool_fn.invoke(tool_args)
                    actions.append(f"调用了 {tool_name}({tool_args})")
                else:
                    result = f"未知工具：{tool_name}"

                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )

        return {
            "output": messages[-1].content,
            "actions": actions,
            "tool_calls_data": tool_calls_data,
        }

    def _run_without_tools(self, prompt: str, question: str) -> str:
        """没有工具的步骤：直接调 LLM"""
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=question),
        ])
        return response.content
