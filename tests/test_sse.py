"""tests/test_sse.py"""
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.sse import router

# 最小化测试 app：只挂 SSE 路由，不触发 lifespan
test_app = FastAPI()
test_app.include_router(router)
client = TestClient(test_app)


def _read_events(response) -> list[dict]:
    """把 SSE 流解析成事件列表"""
    events = []
    event_type = "" 
    for line in response.iter_lines():
        decoded = line.decode() if isinstance(line, bytes) else line
        if decoded.startswith("event: "):
            event_type = decoded[7:]
            # 注释 [7:] 的意思是"从第 7 个字符（event:  的长度）截到末尾"，去掉前缀只留事件名。
        elif decoded.startswith("data: "):
            data = json.loads(decoded[6:])
            # 注释[6:] 去掉 data:  前缀，剩下的 {"node":"..."} 用 json.loads 转成 Python dict。
            events.append({"event": event_type, "data": data})
    return events

class TestWorkflowStream:
    def test_uninitialized(self):
        """vectordb 为 None 时返回 error 事件"""
        with patch("backend.state.vectordb", None):
            # 注释像浏览器一样发一个 GET 请求给
            with client.stream("GET", "/chat/workflow/stream?question=test") as response:
                assert response.status_code == 200
                # 注释确认 HTTP 状态码是 200。
                # 注释 注意 SSE 即使返回错误也是 200——因为错误是包装在 event: error 里的，不是 HTTP 级别的错误。
                events = _read_events(response)
                assert len(events) == 1
                assert events[0]["event"] == "error"
                assert events[0]["data"]["message"] == "索引未初始化"


class TestAgentStream:
    def test_uninitialized(self):
        """vectordb 为 None 时返回 error 事件"""
        with patch("backend.state.vectordb", None):
            with client.stream("GET", "/chat/agent/stream?question=test") as response:
                assert response.status_code == 200
                events = _read_events(response)
                assert len(events) == 1
                assert events[0]["event"] == "error"
                assert events[0]["data"]["message"] == "索引未初始化"

