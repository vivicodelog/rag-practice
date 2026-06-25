"""
对话历史管理（公共模块）。

RAG / NL2SQL / Workflow 共用同一套历史处理逻辑。
"""



def trim_history(
    history: list[dict],
    llm,
    max_rounds: int = 4,
) -> list[dict]:
    """控制历史长度：超出 max_rounds 时，用 LLM 压缩旧轮为摘要。

    history 格式：[{"role": "user"|"assistant", "content": "..."}, ...]

    返回一个消息列表（同样是 dict），压缩后在开头插入一条 system 消息
    写上摘要，后面接最近几轮的完整对话。

    注意：返回的列表**不包含**当前用户的最新问题——
    调用方自己追加，保证灵活性（不同场景可能要加不同格式）。
    """    
    # 1. 如果 history 长度 <= max_rounds，直接原样返回
    #    提示：return history.copy() 副本，避免调用方误改
    #
    # 2. 如果超出，拆成 old（需要压缩）和 recent（保留）
    #    old = history[:-max_rounds]
    #    recent = history[-max_rounds:]
    #
    # 3. 拼压缩 prompt，调用 llm.invoke() 拿摘要
    #    参考 chat() 的写法：
    #      "请将以下对话压缩为一句简短摘要：\n"
    #      遍历 old，问→"问：xxx\n"，答→"答：xxx\n"
    #      summary = llm.invoke(prompt).content
    #
    # 4. 组装返回列表：
    #    [{"role": "system", "content": f"之前的对话摘要：{summary}"}]
    #    + recent（原样展开）
    #
    # 回忆：create_llm() 已经在 agent.py 里配好了 timeout 和 max_retries，
    #       所以直接用 llm.invoke() 不用担心超时重试。
    if len(history) <= max_rounds:
        return history.copy()
    else:
        old = history[:-max_rounds]
        recent = history[-max_rounds:]
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
        return messages