"""测试 main.py — app 创建、路由注册、CORS"""

from fastapi import FastAPI


class TestAppStructure:
    """main.py 模块级代码测试（不触发 lifespan）"""

    def test_app_created(self):
        """app 是 FastAPI 实例，标题版本正确"""
        from backend.main import app
        # 1. isinstance 检查
        # 2. assert title
        # 3. assert version
        assert isinstance(app, FastAPI)
        assert app.title == "RAG-Forge API"
        assert app.version == "1.0.0"

    def test_routes_registered(self):
        """6 个核心路由全部注册"""
        from backend.main import app
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        # 4. 写一个 expected 列表，包含：
        #    "/chat" "/documents" "/health"
        #    "/sessions" "/nl2sql" "/sse/chat"
        # 5. for 循环 assert path in paths
        expected = [
            "/chat",
            "/documents",
            "/health",
            "/sessions",
            "/nl2sql",
            "/chat/workflow/stream",
        ]
        for path in expected:
            assert path in paths

    def test_cors_middleware(self):
        """CORS 中间件已添加"""
        from backend.main import app
        types = [m.cls.__name__ for m in app.user_middleware]
        # 6. assert "CORSMiddleware" in types
        assert "CORSMiddleware" in types