"""
LangChain 代理创建 + 对话管理。
"""

import os

from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek
from rag_forge.agent.tools import get_weather, search_docs
from rag_forge.config import settings


tools = [get_weather, search_docs]

# 从 prompts 目录加载系统提示词
_prompt_path = os.path.join(settings.PROMPTS_DIR, "system.md")
with open(_prompt_path, "r", encoding="utf-8") as _f:
    system_prompt = _f.read().strip()

def create_llm(api_key: str, model: str = "deepseek-chat", temperature: float = 0.1):
    """创建 LLM 实例"""
    return ChatDeepSeek(
        api_key=SecretStr(api_key),
        model=model,
        temperature=temperature,
    )


def build_agent(llm, tools: list, system_prompt: str | None = None):
    from langchain.agents import create_agent
    return create_agent(llm, tools, system_prompt=system_prompt)


def chat(message: str, history: list, agent,llm, max_rounds: int = 4):
    """
    聊天函数（生成器，流式返回）。
    """
    """ChatInterface 的回调函数。
    message: 用户输入的字符串
    history: list[dict]，格式为 [{"role": "user/assistant", "content": "..."}]
    yield: 流式返回回答文本"""
    MAX_ROUNDS = max_rounds

    if len(history) > MAX_ROUNDS:
        old = history[:-MAX_ROUNDS]#旧的部分（需要压缩） # 从头开始到 end（不包含 end）
        recent = history[-MAX_ROUNDS:]#新的部分（需要保留）# 最后 n 个元素
                                                       
        summary_prompt = "请将以下对话压缩为一句简短摘要：\n"
        for msg in old:
            if msg["role"] == "user":
                summary_prompt += f"问：{msg['content']}\n"
            else:
                summary_prompt += f"答：{msg['content']}\n"
        summary = llm.invoke(summary_prompt).content

        messages = [{"role": "system", "content": f"之前的对话摘要：{summary}"}]
        for msg in recent:
            messages.append({"role": msg["role"], "content": msg["content"]})
    else:
        messages = []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    for event in agent.stream(
        {"messages": messages},
        stream_mode="values",#返回完整的事件值
    ):#流式调用 AI 代理
        last_msg = event["messages"][-1]#获取最新消息
        msg_type = getattr(last_msg, "type", "")
        if msg_type in ("human", "tool"):
            continue
        if msg_type == "ai" and getattr(last_msg, "tool_calls", None):
            continue## AI 在调用工具，不是最终回答
        if hasattr(last_msg, "content") and last_msg.content:
            yield last_msg.content#yield - 生成器，逐步输出内容

