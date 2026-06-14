"""
请求/响应数据模型。

定义 API 的数据结构，FastAPI 会自动校验参数类型。
"""

from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    history: Optional[List[dict]] = []


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
