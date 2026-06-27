"""NL2SQL 路由"""

from fastapi import APIRouter

from backend.schemas import NL2SQLRequest, NL2SQLResponse
from backend.database import save_message
from nl2sql.agent import nl2sql

router = APIRouter(tags=["nl2sql"])


@router.post("/nl2sql", response_model=NL2SQLResponse)
def nl2sql_chat(request: NL2SQLRequest):
    result = nl2sql(request.question, request.history or [])
    if request.session_id:
        save_message(request.session_id, "user", request.question)
        summary = f"SQL: {result['sql']}\n"
        if not result["error"]:
            summary += f"查询结果：{len(result['rows'])} 条记录"
        else:
            summary += f"错误：{result['error']}"
        save_message(request.session_id, "assistant", summary, sql=result["sql"], cols=result.get("columns"), rows_data=result.get("rows"), error=result.get("error"))
    return NL2SQLResponse(**result)

