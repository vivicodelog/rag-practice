"""
LangChain 代理创建 + 对话管理。
"""

import os
import uuid

from loguru import logger
from pydantic import SecretStr
from langchain_deepseek import ChatDeepSeek
from rag_forge.history import trim_history
from rag_forge.agent.tools import get_weather, query_database, search_docs, trace_id_var
from rag_forge.config import settings


tools = [get_weather, search_docs,query_database]

# 从 prompts 目录加载系统提示词
_prompt_path = os.path.join(settings.PROMPTS_DIR, "system.md")
with open(_prompt_path, "r", encoding="utf-8") as _f:
    system_prompt = _f.read().strip()

def create_llm(
    api_key: str,
    model: str | None = None,
    temperature: float | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
):
    """创建 LLM 实例，支持超时和重试。

    各参数默认值走 settings 里的配置，调用方可以按需覆盖。
    这样：
      - 大部分代码不传参，直接用全局配置
      - 需要特殊值的（比如 evaluation 里 judge 用 temperature=0）可以覆盖
    """
    # 你的任务：
    # 1. model 为 None 时改成 settings.LLM_MODEL
    # 2. temperature / timeout / max_retries 同理，None 就走 settings 的默认值
    # 3. 把这些参数全部传给 ChatDeepSeek(...)
    #
    # ChatDeepSeek 继承自 langchain 的 ChatOpenAI，原生支持：
    #   - timeout: 请求超时秒数（传 int）
    #   - max_retries: 遇到网络/429/5xx 时自动重试次数（传 int）
    #   直接当参数传进去就行
    #
    # 小提示：
    #   settings.LLM_TIMEOUT 是 int，ChatDeepSeek 的 timeout 参数也接受 int
    #   SecretStr(api_key) 别忘了
    if model is None:
        model = settings.LLM_MODEL
    if temperature is None:
        temperature = settings.LLM_TEMPERATURE
    if timeout is None:
        timeout = settings.LLM_TIMEOUT
    if max_retries is None:
        max_retries = settings.LLM_MAX_RETRIES
    return ChatDeepSeek(
        api_key=SecretStr(api_key),
        model=model,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
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
    trace_id = f"trace_{uuid.uuid4().hex[:8]}"
    trace_id_var.set(trace_id)
    logger.info(f"[{trace_id}] 收到用户问题: {message[:50]}{'…' if len(message) > 50 else ''}")
    messages = trim_history(history,llm, max_rounds)
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
    logger.info(f"[{trace_id}] LLM 回答完成")

