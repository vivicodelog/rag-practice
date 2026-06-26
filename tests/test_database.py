"""测试 SQLite 会话存储层"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import get_db, init_db, create_session, get_sessions, \
    get_session, get_messages, save_message, delete_session

@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建内存数据库"""
    # 重置单例，确保拿到新连接
    import backend.database
    backend.database._db = None
    db = get_db(":memory:")
    init_db(db)
    yield
    db.close()
    backend.database._db = None

def test_create_session():
    """创建会话后返回包含 id/mode/title 的 dict"""
    s = create_session("agent", title="测试会话")
    assert s["id"] is not None
    assert s["mode"] == "agent"
    assert s["title"] == "测试会话"

def test_get_sessions():
    """按 mode 列出会话，含 message_count"""
    s1 = create_session("agent", title="对话A")
    s2 = create_session("agent", title="对话B")
    create_session("workflow", title="工作流")  # 不同 mode，不应返回

    sessions = get_sessions("agent")
    assert len(sessions) == 2
    assert sessions[0]["title"] == "对话B"  # 按 updated_at DESC，后创建的在前面

def test_get_session():
    """按 id 获取单条会话"""
    s = create_session("agent", title="详情测试")
    got = get_session(s["id"])
    assert got is not None
    assert got["title"] == "详情测试"
    assert got["mode"] == "agent"

    # 查不存在的 id 返回 None
    assert get_session("不存在的id") is None

def test_get_messages():
    """按 session_id 获取消息列表，按时间正序"""
    s = create_session("agent")
    save_message(s["id"], "user", "你好")
    save_message(s["id"], "assistant", "你好！")

    msgs = get_messages(s["id"])
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["role"] == "assistant"

def test_delete_session():
    """删除会话"""
    s = create_session("agent")
    save_message(s["id"], "user", "你好")
    save_message(s["id"], "assistant", "你好！")

    delete_session(s["id"])
    assert get_session(s["id"]) is None
    assert get_messages(s["id"]) == []