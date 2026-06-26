"""汇总所有子路由"""
from fastapi import APIRouter

from backend.routers.chat import router as chat_router
from backend.routers.documents import router as documents_router
from backend.routers.nl2sql import router as nl2sql_router
from backend.routers.sessions import router as sessions_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(documents_router)
router.include_router(nl2sql_router)
router.include_router(sessions_router)
