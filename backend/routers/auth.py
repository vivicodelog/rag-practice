from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import bcrypt

from backend.database import create_user, get_user_by_id, get_user_by_username
from backend.auth import create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: AuthRequest):
    if get_user_by_username(body.username):
        raise HTTPException(400, detail="用户名已存在")
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    create_user(body.username, password_hash)
    return {"ok": True}


@router.post("/login")
def login(body: AuthRequest):
    user = get_user_by_username(body.username)
    if not user:
        raise HTTPException(401, detail="用户名或密码错误")
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, detail="用户名或密码错误")
    token = create_token(user["id"])
    return {"token": token, "user_id": user["id"]}

@router.post("/logout")
def logout():
    return {"ok": True}


@router.get("/me")
def me(user_id: str = Depends(get_current_user)):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, detail="User not found")
    return {"id": user["id"], "username": user["username"], "created_at": user["created_at"]}