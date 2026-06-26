"""NL2SQL 路由"""

from fastapi import APIRouter

from backend.schemas import NL2SQLRequest, NL2SQLResponse
from backend.database import save_message
from nl2sql.agent import nl2sql

router = APIRouter(tags=["nl2sql"])


@router.post("/nl2sql", response_model=NL2SQLResponse)
def nl2sql_chat(request: NL2SQLRequest):
    """NL2SQL：自然语言 → SQL → 查询结果"""
    result = nl2sql(request.question, request.history or [])
    if request.session_id:
        save_message(request.session_id, "user", request.question)
        save_message(request.session_id, "assistant", result["sql"])
    return NL2SQLResponse(**result)
