import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.database import get_db, get_messages, init_db
from backend.routers.nl2sql import router

mock_data = {
    "sql": "SELECT name, country FROM authors",
    "columns": ["name", "country"],
    "rows": [["张三", "中国"]],
    "error": ""
}

@pytest.fixture(autouse=True)
def clean_db():
    import backend.database
    backend.database._db = None
    db = get_db(":memory:")
    init_db(db)
    yield
    db.close()
    backend.database._db = None

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    return TestClient(app)

@patch("backend.routers.nl2sql.nl2sql", return_value=mock_data)
def test_nl2sql_without_session(mock_nl2sql, client):
    resp = client.post("/nl2sql", json={"question": "列出所有作者"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sql"] == "SELECT name, country FROM authors"

@patch("backend.routers.nl2sql.nl2sql", return_value=mock_data)
def test_nl2sql_with_session(mock_nl2sql,client):
                            #   ↑参数名不叫 mock_nl2sql 都可以，叫 _ 也行，但位置必须占住
    resp = client.post("/nl2sql", json={"question": "列出所有作者", "session_id": "123"})
    assert resp.status_code == 200
    msgs = get_messages("123")
    assert len(msgs) == 2                     # user + assistant
    assert msgs[1]["sql"] == "SELECT name, country FROM authors"


error_mock = {
    "sql": "SELECT name, country FROM authors",
    "columns": ["name", "country"],
    "rows": [],
    "error": "数据库连接错误"
}
@patch("backend.routers.nl2sql.nl2sql", return_value=error_mock)
def test_nl2sql_error(mock_nl2sql,client):
    resp = client.post("/nl2sql", json={"question": "列出所有作者", "session_id": "123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == "数据库连接错误"
