"""会话管理路由（多轮对话）"""

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import get_current_user
from backend.database import (
    create_session, get_sessions, get_session,
    get_messages, save_message, delete_session,
)
from backend.schemas import SessionCreateRequest, SessionItem, SessionDetail

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionItem)
def create(request: SessionCreateRequest, user_id: str = Depends(get_current_user)):
    """新建会话"""
    s = create_session(request.mode, request.title or "新对话", user_id)
    return s


@router.get("", response_model=list[SessionItem])
def list_sessions(mode: str, user_id: str = Depends(get_current_user)):
    """按 mode 获取会话列表"""
    return get_sessions(mode, user_id)


@router.get("/{session_id}", response_model=SessionDetail)
def get(session_id: str, user_id: str = Depends(get_current_user)):
    """获取会话详情（含消息历史）"""
    s = get_session(session_id, user_id)
    if s is None:
        raise HTTPException(404, detail="会话不存在")
    msgs = get_messages(session_id)
    return SessionDetail(**s, messages=msgs)


@router.delete("/{session_id}")
def delete(session_id: str, user_id: str = Depends(get_current_user)):
    """删除会话"""
    delete_session(session_id, user_id)
    return {"ok": True}
