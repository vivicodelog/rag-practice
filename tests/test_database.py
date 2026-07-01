"""测试 SQLite 会话存储层"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import get_db, init_db, create_session, get_sessions, \
    get_session, get_messages, save_message, delete_session


from backend.database import create_user

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
    user = create_user("test", "hash")
    s1 = create_session("agent", title="对话A", user_id=user["id"])
    s2 = create_session("agent", title="对话B", user_id=user["id"])
    create_session("workflow", title="工作流", user_id=user["id"])  # 不同 mode，不应返回

    sessions = get_sessions("agent", user["id"])
    assert len(sessions) == 2
    assert sessions[0]["title"] == "对话B"  # 按 updated_at DESC，后创建的在前面

def test_get_session():
    """按 id 获取单条会话"""
    user = create_user("test", "hash")
    s = create_session("agent", title="详情测试", user_id=user["id"])
    got = get_session(s["id"], user["id"])
    assert got is not None
    assert got["title"] == "详情测试"
    assert got["mode"] == "agent"

    # 查不存在的 id 返回 None
    assert get_session("不存在的id", user["id"]) is None

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
    user = create_user("test", "hash")
    s = create_session("agent",'',user_id=user["id"])
    save_message(s["id"], "user", "你好")
    save_message(s["id"], "assistant", "你好！")

    delete_session(s["id"], user["id"])
    assert get_session(s["id"], user["id"]) is None
    assert get_messages(s["id"]) == []

def test_init_db_idempotent():
    """init_db 调两次不崩（第二次 ALTER TABLE 列已存在→被 except 接住）"""
    init_db()   # 第一次：正常建表 + ALTER TABLE 成功
    init_db()   # 第二次：ALTER TABLE 报错 → except pass


def test_save_and_read_nl2sql_fields():
    """存 NL2SQL 专用字段（sql/cols/rows_data），读出后 columns/rows 解析正确"""
    user = create_user("test", "hash")
    s = create_session("agent", user_id=user["id"])
    
    save_message(s["id"], "assistant", "结果如下",
                 sql="SELECT * FROM users",
                 cols=["id", "name"],
                 rows_data=[["1", "张三"], ["2", "李四"]])
    
    msgs = get_messages(s["id"])
    assert len(msgs) == 1
    assert msgs[0]["sql"] == "SELECT * FROM users"
    assert msgs[0]["columns"] == ["id", "name"]
    assert msgs[0]["rows"] == [["1", "张三"], ["2", "李四"]]
