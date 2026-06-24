"""
对话历史压缩 trim_history 的单元测试。

逻辑回顾：
    没超出 max_rounds → 原样返回副本
    超出 → 旧的用 LLM 压成摘要 + 保留最近几轮完整
"""

import sys
sys.path.insert(0, "d:/rag-project")

from unittest.mock import MagicMock
from rag_forge.history import trim_history


def test_within_limit_returns_copy():
    """<= max_rounds：不调 LLM，原样返回副本。"""
    llm = MagicMock()
    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮你的"},
    ]
    trimmed = trim_history(history, llm, max_rounds=4)

    assert trimmed is not history          # 是副本
    assert len(trimmed) == 2
    assert trimmed == history              # 内容一样
    llm.invoke.assert_not_called()         # 没调 LLM


def test_compress_when_exceeds_limit():
    """> max_rounds：旧轮压缩成摘要，最近 N 轮保留。"""
    llm = MagicMock()
    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮你的"},
        {"role": "user", "content": "你好,今天北京天气怎么样"},
        {"role": "assistant", "content": "北京天气晴朗"},
        {"role": "user", "content": "上海今天天气怎么样"},
        {"role": "assistant", "content": "上海天气晴朗"},
        {"role": "user", "content": "明天的北京天气怎么样"},
        {"role": "assistant", "content": "北京天气也是晴朗"},
    ]
    trimmed = trim_history(history, llm, max_rounds=4)

    llm.invoke.assert_called_once()               # 调了 LLM 做压缩
    assert len(trimmed) == 5                       # 1 条摘要 + 4 条最近
    assert trimmed[0]["role"] == "system"          # 第一条是 system 摘要
    assert trimmed[1:] == history[-4:]             # 后 4 条是最近对话


def test_empty_history():
    """空历史返回空列表。"""
    llm = MagicMock()
    trimmed = trim_history([], llm, max_rounds=4)

    assert trimmed == []
    llm.invoke.assert_not_called()


def test_exactly_at_limit():
    """刚好等于 max_rounds，不压缩。"""
    llm = MagicMock()
    history = [
        {"role": "user", "content": "A"},
        {"role": "assistant", "content": "B"},
        {"role": "user", "content": "C"},
        {"role": "assistant", "content": "D"},
    ]
    trimmed = trim_history(history, llm, max_rounds=4)

    assert len(trimmed) == 4
    assert trimmed == history
    llm.invoke.assert_not_called()
