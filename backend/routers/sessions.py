"""会话管理路由（多轮对话）"""

from fastapi import APIRouter, HTTPException

from backend.database import (
    create_session, get_sessions, get_session,
    get_messages, save_message, delete_session,
)
from backend.schemas import SessionCreateRequest, SessionItem, SessionDetail

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionItem)
def create(request: SessionCreateRequest):
    """新建会话"""
    s = create_session(request.mode)
    return s


@router.get("", response_model=list[SessionItem])
def list_sessions(mode: str):
    """按 mode 获取会话列表"""
    return get_sessions(mode)


@router.get("/{session_id}", response_model=SessionDetail)
def get(session_id: str):
    """获取会话详情（含消息历史）"""
    s = get_session(session_id)
    if s is None:
        raise HTTPException(404, detail="会话不存在")
    msgs = get_messages(session_id)
    return SessionDetail(**s, messages=msgs)


@router.delete("/{session_id}")
def delete(session_id: str):
    """删除会话"""
    delete_session(session_id)
    return {"ok": True}
