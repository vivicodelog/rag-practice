"""
请求/响应数据模型。

定义 API 的数据结构，FastAPI 会自动校验参数类型。
"""

from pydantic import BaseModel, field_validator
from typing import Optional, List


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    history: Optional[List[dict]] = []
    session_id: Optional[str] = None


class SourceItem(BaseModel):
    """来源文档信息"""
    filename: str
    score: float
    content: str


class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str
    sources: List[SourceItem]


class UploadResponse(BaseModel):
    """上传文档响应"""
    success: bool
    message: str
    total_docs: int


class DeleteRequest(BaseModel):
    """删除文档请求"""
    filename: str


class DeleteResponse(BaseModel):
    """删除文档响应"""
    success: bool
    message: str

    
class WorkflowStep(BaseModel):
    """Workflow 步骤日志"""
    role: str
    status: str
    input: str
    actions: Optional[List[str]] = None
    output: Optional[str] = None

class WorkflowResponse(BaseModel):
    """Workflow 聊天响应"""
    answer: str
    steps: List[WorkflowStep]


# ── NL2SQL ──────────────────────────────────────────────

class NL2SQLRequest(BaseModel):
    """NL2SQL 查询请求

    用户发一个自然语言问题，比如"列出所有作者的姓名和国籍"
    """
    question: str # ← 用户的问题
    history: Optional[List[dict]] = []
    session_id: Optional[str] = None


class NL2SQLResponse(BaseModel):
    """NL2SQL 查询响应

    nl2sql() 返回三样东西：
      - sql: LLM 生成的 SQL 语句（展示给用户看）
      - columns: 查询结果的列名列表（给表格做表头）
      - rows: 查询结果的数据行，每行是一个 list（给表格填数据）
    """
    sql: str                    # ← 生成的 SQL
    columns: List[str]          # ← 列名，比如 ["name", "country"]
    rows: List[List]            # ← 数据，比如 [["张三", "中国"], ["李四", "美国"]]
    error: Optional[str] = None # ← 错误信息（没有错误就是 None）
    explanation: Optional[str] = None  # ← SQL 大白话解释（比如"查询所有作者的名字和国籍"）

class SessionCreateRequest(BaseModel):
    mode: str
    title: Optional[str] = "新对话"

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        # v 是传入的 mode 值
        # 如果 v 不在 ['agent', 'workflow', 'nl2sql'] 里
        #   抛 ValueError，Pydantic 自动转 400
        # 否则返回 v
        if v not in ['agent', 'workflow', 'nl2sql']:
            raise ValueError("mode must be one of ['agent', 'workflow', 'nl2sql']")
        return v

class SessionItem(BaseModel):
    """会话信息"""
    id: str
    mode: str
    title: str
    message_count: int
    created_at: str
    updated_at: str

class SessionDetail(BaseModel):
    """会话详情"""
    id: str
    mode: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
    messages: List[dict] = []