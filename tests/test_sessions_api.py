"""测试会话 CRUD API"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.sessions import router
from backend.database import get_db, init_db
from backend.auth import create_token
from backend.database import create_user




@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建内存数据库"""
    import backend.database
    backend.database._db = None
    db = get_db(":memory:")
    init_db(db)
    yield
    db.close()
    backend.database._db = None


@pytest.fixture
def app():
    """建一个轻量 FastAPI app，只包含 sessions 路由"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """创建一个用户，返回 Authorization header"""
    user = create_user("testuser", "not-used-in-test")
    token = create_token(user["id"])
    return {"Authorization": f"Bearer {token}"}

class TestCreateSession:
    def test_create_session(self, client, auth_headers):
        """POST /sessions 返回新建的会话"""
        resp = client.post("/sessions", json={"mode": "agent"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "agent"
        assert data["title"] == "新对话"
        assert "id" in data

    def test_create_session_invalid_mode(self, client, auth_headers):
        """无效 mode 返回 400（SQLite CHECK 约束拒绝）"""
        resp = client.post("/sessions", json={"mode": "invalid"}, headers=auth_headers)
        assert resp.status_code == 422


class TestListSessions:
    def test_list_sessions(self, client, auth_headers):
        """GET /sessions?mode=agent 返回过滤后的列表"""
        client.post("/sessions", json={"mode": "agent"}, headers=auth_headers)
        client.post("/sessions", json={"mode": "workflow"}, headers=auth_headers)
        client.post("/sessions", json={"mode": "agent"}, headers=auth_headers)

        resp = client.get("/sessions?mode=agent", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(s["mode"] == "agent" for s in data)

    def test_list_sessions_empty(self, client, auth_headers):
        """没有会话时返回空列表"""
        resp = client.get("/sessions?mode=nl2sql", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetSession:
    def test_get_session(self, client, auth_headers):
        """GET /sessions/{id} 返回会话详情（含消息）"""
        created = client.post("/sessions", json={"mode": "agent"}, headers=auth_headers).json()
        resp = client.get(f"/sessions/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert "messages" in data
        assert data["messages"] == []

    def test_get_session_not_found(self, client, auth_headers):
        """不存在的 id 返回 404"""
        resp = client.get("/sessions/non-existent", headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteSession:
    def test_delete_session(self, client, auth_headers):
        """DELETE /sessions/{id} 删除成功"""
        created = client.post("/sessions", json={"mode": "agent"}, headers=auth_headers).json()
        resp = client.delete(f"/sessions/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200

        # 删后再查返回 404
        resp = client.get(f"/sessions/{created['id']}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_session_idempotent(self, client, auth_headers):
        """删不存在的 id 不会报错"""
        resp = client.delete("/sessions/ghost-id", headers=auth_headers)
        assert resp.status_code == 200
