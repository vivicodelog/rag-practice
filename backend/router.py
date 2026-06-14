"""
API 路由。

核心就是调 rag_forge 的函数。
"""

from datetime import datetime
import json
import os
import traceback
from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger

from backend.workflow import Workflow, WorkflowNode
from rag_forge.agent.agent import system_prompt
from rag_forge.agent.tools import get_weather, review_result, search_docs
from rag_forge.config import settings
from rag_forge.data.loader import FileSource, build_vectorstore
from rag_forge.embedding.embed import create_embeddings
from rag_forge.retrieval.hybrid import hybrid_search
from rag_forge.data.manifest import load_manifest, save_manifest, sync_manifest

import backend.state as state
from backend.schemas import ChatRequest, ChatResponse, SourceItem, UploadResponse, WorkflowResponse
from rag_forge.service import rebuild_vectorstore
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from rag_forge.config import settings

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """问答接口：Agent 模式，LLM 自主选择工具"""
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    try:
        # 1. 把工具绑给 LLM
        llm_with_tools = state.llm.bind_tools([get_weather, search_docs])

        # 2. 准备消息（用 system.md，LLM 才知道有工具可用）
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.question),
        ]

        sources = []  # 来源列表，search_docs 搜到时在这里攒

        # 3. 工具调用循环（最多 3 轮，防死循环）
        for _ in range(3):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break  # 没调工具 → 最终回答

            # 4. 执行每一个工具调用
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"].lower()
                tool_args = tool_call["args"]

                if tool_name == "search_docs":
                    result = search_docs.invoke(tool_args)
                    # 搜到了有效内容 → 顺手攒来源
                    if result not in ("未找到相关文档", "知识库尚未初始化，请先上传文档"):
                        raw = hybrid_search(
                            query=tool_args["query"],
                            vectordb=state.vectordb,
                            all_chunks=state.all_chunks,
                            top_k=6,
                            reranker=state.reranker,
                        )
                        sources = [
                            SourceItem(
                                filename=os.path.basename(s) if s else "未知",
                                score=score,
                                content=c[:200],
                            )
                            for c, score, s in raw
                        ]
                elif tool_name == "get_weather":
                    result = get_weather.invoke(tool_args)
                else:
                    result = f"未知工具：{tool_name}"

                messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

        # 5. 最终回答
        answer = messages[-1].content

        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"聊天接口异常：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
def list_documents():
    """列出所有文档"""
    manifest = sync_manifest(settings.DATA_DIR, settings.MANIFEST_FILE)
    filenames = [item["filename"] for item in manifest]
    return {"documents": filenames}
@router.get("/documents/details")
def list_documents_detail():
    """返回文档列表表格"""
    manifest = load_manifest(settings.MANIFEST_FILE)
    print(manifest)
    if not manifest:
        return []
    rows = []
    for item in manifest:
        size_kb = item["size"] / 1024
        rows.append({
            "filename": item["filename"],
            "size": f"{size_kb:.1f} KB",
            "upload_time": item["upload_date"][:19]
        })
    return {"documents": rows}

@router.get("/health")
def health():
    """健康检查"""
    return {
        "status": "ok",
        "vectordb": state.vectordb is not None,
        "chunks": len(state.all_chunks),
        "reranker": state.reranker is not None,
    }
@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """保存文件 → 更新清单 → 重建向量库"""
    #drop = update_delete_dropdown
    try:
        if file is None:
            return "请选择文件"        
        # FastAPI 版：直接从 UploadFile 对象读内容 
        # if isinstance(file, str):#isinstance(变量, 类型) 是 Python 里用来检查一个变量是不是某种类型的函数
        #     original_name = os.path.basename(file)
        #     original_path = file
        #     with open(original_path, "rb") as f:
        #         content = f.read()   # ← 直接写，不需要临时文件
        #     file_path = os.path.join(settings.DATA_DIR, original_name)           
        # else:#这是在拼一个目标路径，意思是"我要把这个上传的文件存到 DATA_DIR 下面"，并不是"从已有文档里找
        if file.filename is None:
            raise HTTPException(400, detail="上传文件名称为空")
        original_name = file.filename
        file_path = os.path.join(settings.DATA_DIR, file.filename)
        
        content = await file.read()
          
        with open(file_path, "wb") as f:
                f.write(content)
        filename = original_name
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('txt', 'pdf', 'docx', 'md', 'doc'):
            return "仅支持 TXT、PDF、DOCX、MD 文件" 

        manifest = load_manifest(settings.MANIFEST_FILE)
        if any(item["filename"] == filename for item in manifest):
            return f"文件 '{filename}' 已存在，请先删除旧文件"        
         
        manifest.append({
            "filename": filename,
            "size": os.path.getsize(file_path),
            "upload_date": datetime.now().isoformat()
        })
        save_manifest(manifest, settings.MANIFEST_FILE)

        try:
            state.vectordb,state.all_chunks = rebuild_vectorstore(state.embeddings)
        except Exception:
            # 重建失败 → 回滚
            if os.path.exists(file_path):
                os.remove(file_path)
            manifest = load_manifest(settings.MANIFEST_FILE)
            manifest = [item for item in manifest if item["filename"] != filename]
            save_manifest(manifest, settings.MANIFEST_FILE)
            raise

        return f"✓ 文件 '{filename}' 上传成功，向量库已重建"
    except Exception as e:
        traceback.print_exc()
        return f"❌ 上传失败：{type(e).__name__}: {e}"

@router.delete("/delete")
def delete_document(filename):
    try:
        if not filename:
            return "请选择要删除的文件"

        filepath = os.path.join(settings.DATA_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        state.vectordb, state.all_chunks = rebuild_vectorstore(state.embeddings)

        return f"✓ 文件 '{filename}' 已删除，向量库已重建"
    except Exception as e:
        traceback.print_exc()
        return f"❌ 删除失败：{type(e).__name__}: {e}"
@router.delete("/delete/choices")
def get_delete_choices():
    """返回文件名列表（供下拉框使用）"""
    return [item["filename"] for item in load_manifest(settings.MANIFEST_FILE)]


@router.post("/chat/workflow", response_model=WorkflowResponse)
def chat_workflow(request: ChatRequest):
#     检查 state.vectordb 是否初始化（跟 /chat 一样）
# 读取 prompts/researcher.md 和 prompts/writer.md
# 创建两个 WorkflowNode
# 创建 Workflow，传入 state.llm
# 调 workflow.run(question)
# 返回结果
    if state.vectordb is None:
        raise HTTPException(status_code=503, detail="系统尚未初始化完成")

    # 读 prompt 文件...   
    researcher_prompt = state.researcher_prompt
    writer_prompt = state.writer_prompt
    reviewer_prompt = state.reviewer_prompt
    # 组装节点...
    # Researcher：有工具，取文本
    researcher_node = WorkflowNode(
        role="researcher",
        tools=[search_docs],
        prompt=researcher_prompt,
        output_key="research",
        output_type="text",
    )
    # Writer：没有工具
    writer_node = WorkflowNode(
        role="writer",
        tools=[],
        prompt=writer_prompt,
        output_key="answer",
    )
    # Reviewer：有工具，取结构化数据
    reviewer_node = WorkflowNode(
        role="reviewer",
        tools=[review_result],
        prompt=reviewer_prompt,
        output_key="answer",
        output_type="tool",
    )
    nodes = [
            researcher_node,
            writer_node,
            reviewer_node
    ]

    # 跑 Workflow...（先创建实例，再调用 run）
    workflow = Workflow(nodes=nodes, llm=state.llm)
    result = workflow.run(request.question)
    return WorkflowResponse(answer=result["answer"], steps=result["steps"])










