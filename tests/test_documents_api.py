import tempfile

import pytest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.routers.documents import router

from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    return TestClient(app)


mock_data = [
    {
        "filename": "test.txt",
        "size": 1024,
        "upload_date": "upload_date"
    }
]
mock_data_documents = [
    {
        "filename": "filename",
        "size": 1024,
        "upload_date": "upload_date"
        
    }
 ]
class TestDocumentsAPI:
    @patch("backend.routers.documents.sync_manifest", return_value=mock_data)
    def test_documents_api(self, mock_sync_manifest, client):
        resp = client.get("/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"documents": ["test.txt"]}
        
    def test_documents_detail_error(self, client):
         with patch("backend.routers.documents.load_manifest", return_value=[]):      
            resp = client.get("/documents/details")
            data = resp.json()
            assert data == []

    @patch("backend.routers.documents.load_manifest", return_value = mock_data_documents)
    def test_documents_detail(self, mock_sync_manifest, client):
        resp = client.get("/documents/details")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"documents": [
            {"filename": "filename", "size": "1.0 KB", "upload_time": "upload_date"}
        ]}

    @patch("backend.routers.documents.load_manifest", return_value = mock_data)
    def test_delete_choices(self, mock_sync_manifest, client):
        resp = client.get("/delete/choices")
        assert resp.status_code == 200
        data = resp.json()
        assert data == ["test.txt"]
         
   
    @patch("backend.routers.documents.rebuild_vectorstore", return_value=("fake_db", ["chunk1"]))
    @patch("os.remove")
    @patch("os.path.exists", return_value=True) 
    #注释：@patch 顺序法则——离函数最近的 decorator，参数排最前（self 之后）
    def test_delete_document(self, mock_exists, mock_remove, mock_rebuild, client):
        resp = client.delete("/delete?filename=test.txt")
        data = resp.json()
        assert resp.status_code == 200
        assert "已删除" in data  
     
    def test_upload_invalid_extension(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.routers.documents.settings.DATA_DIR", tmpdir):
                resp = client.post("/upload", files={"file": ("test.exe", b"hello world")})
                assert resp.status_code == 200
                assert resp.json() == "仅支持 TXT、PDF、DOCX、MD 文件"
    def test_upload_success(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.routers.documents.settings.DATA_DIR", tmpdir):
                with patch("backend.routers.documents.load_manifest", return_value=[]):
                    with patch("backend.routers.documents.save_manifest"):
                        with patch("backend.routers.documents.rebuild_vectorstore",
                                return_value=("fake_db", ["chunk1"])):
                            resp = client.post("/upload", files={"file": ("test.txt", b"hello world")})
                            assert resp.status_code == 200
                            assert "上传成功" in resp.json()



class TestHealthAPI:
    
    @pytest.fixture(autouse=True)
    def mock_state(self):
        with patch("backend.state.vectordb", "fake"):
            with patch("backend.state.all_chunks", ["chunk1"]):
                with patch("backend.state.reranker", "fake"):
                    yield

    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["vectordb"] is True
        assert data == {"status": "ok", "vectordb": True, "chunks": 1, "reranker": True}

