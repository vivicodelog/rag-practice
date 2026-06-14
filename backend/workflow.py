"""
Workflow 编排核心。

Researcher → Writer（→ Reviewer）串行执行，
每一步的产出传给下一步。
"""

from typing import Any, List

from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from rag_forge.agent.tools import search_docs, get_weather


class WorkflowNode:
    """一个步骤"""
    def __init__(self, role: str, tools: list, prompt: str, output_key: str):
        self.role = role              # "researcher" | "writer"
        self.tools = tools            # 绑定的工具函数列表
        self.prompt = prompt          # 系统提示词
        self.output_key = output_key  # 产出存到 results[output_key]


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
            prompt_text = node.prompt
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
                output = result["output"]
                step_log["actions"] = result["actions"]
            else:
                output = self._run_without_tools(prompt_text, question)

            # 3. 存结果
            results[node.output_key] = output
            step_log["status"] = "done"
            step_log["output"] = output
            steps.append(step_log)

            logger.info(f"[Workflow] 完成: {node.role}")

        return {
            "answer": results.get("answer", ""),
            "steps": steps,
        }

    def _run_with_tools(self, prompt: str, question: str, tools: list) -> dict:
        """有工具的步骤：调 Agent，处理工具调用循环"""
        llm_with_tools = self.llm.bind_tools(tools)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=question),
        ]

        actions = []  # 记录调了哪些工具

        for _ in range(3):   # 最多 3 轮工具调用
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break  # 没调工具 → 最终回答

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"].lower()
                tool_args = tool_call["args"]

                if tool_name == "search_docs":
                    result = search_docs.invoke(tool_args)
                    actions.append(f"调用了 search_docs(query={tool_args['query']})")
                elif tool_name == "get_weather":
                    result = get_weather.invoke(tool_args)
                    actions.append(f"调用了 get_weather(city={tool_args['city']})")
                else:
                    result = f"未知工具：{tool_name}"

                messages.append(
                    ToolMessage(content=result, tool_call_id=tool_call["id"])
                )

        return {"output": messages[-1].content, "actions": actions}

    def _run_without_tools(self, prompt: str, question: str) -> str:
        """没有工具的步骤：直接调 LLM"""
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=question),
        ])
        return response.content
