"""测试认证 API"""

import pytest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.database import get_db, init_db
from backend.routers.auth import router

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    """建一个轻量 FastAPI app，只包含 auth 路由"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestRegister:
    def test_register(self, client):
        """POST /register"""
        resp = client.post("/auth/register", json={"username": "user","password":"123456"})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"ok": True}
    def test_register_duplicate(self, client):
        """重复用户名返回 400"""
        client.post("/auth/register", json={"username": "user", "password": "123456"})
        resp = client.post("/auth/register", json={"username": "user", "password": "123456"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "用户名已存在"

    
class TestLogin:
    def test_login_user_not_found(self, client):
        """不存在的用户返回 401"""
        resp = client.post("/auth/login", json={"username": "user", "password": "123456"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "用户名或密码错误"

    def test_login_success(self, client):
        """先注册再登录，拿到 token"""
        client.post("/auth/register", json={"username": "user", "password": "123456"})
        resp = client.post("/auth/login", json={"username": "user", "password": "123456"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user_id"] is not None

    def test_login_wrong_password(self, client):
        """密码错误返回 401"""
        client.post("/auth/register", json={"username": "user", "password": "123456"})
        resp = client.post("/auth/login", json={"username": "user", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "用户名或密码错误"


class TestLogout:
    def test_logout(self, client):
        """POST /logout"""
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"ok": True}

class TestMe:
    def test_me_without_token(self, client):
        """没有 token 返回 401"""
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing or invalid token"


    def test_me_with_invalid_token(self, client):
        """无效 token 返回 401"""
        resp = client.get("/auth/me", headers={"Authorization": "Bearer fake-token"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"


    def test_me_success(self, client):
        """先注册登录，拿到 token 后查自己"""
        client.post("/auth/register", json={"username": "user", "password": "123456"})
        login_resp = client.post("/auth/login", json={"username": "user", "password": "123456"})
        token = login_resp.json()["token"]

        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "user"
        assert "id" in data
        assert "created_at" in data

