import jwt
from datetime import datetime, timedelta, timezone

from rag_forge.config import settings

from fastapi import Request, HTTPException

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    # 注释   algorithm="HS256"是对称加密，同一个 secret 加解密
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        return None

def get_current_user(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth.removeprefix("Bearer ")
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id
