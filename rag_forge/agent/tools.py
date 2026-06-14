"""
LangChain 工具函数：get_weather + search_docs
"""
import contextvars
import json
import os

from loguru import logger
from langchain_core.tools import tool
import requests

# trace_id 上下文变量，贯穿一次问答全流程
#name: str = "张三"
#  ↑      ↑    ↑
# 变量名  类型  值
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
#      ↑                    ↑                          ↑
#    变量名                类型                      值（创建的ContextVar对象）
#变量名（你代码中使用的名字）：类型注解 （给ide看的）字符串类型的上下文变量  = 实际创建 真正创建对象的代码
#Python 的 contextvars（上下文变量） 模块  创建一个"全局变量"，但只在当前请求/任务的上下文中有效，不会互相干扰
from rag_forge.retrieval.hybrid import hybrid_search
from rag_forge.config import settings

# 从 prompts 目录加载工具前缀提示
_TOOL_PREFIX_PATH = os.path.join(settings.PROMPTS_DIR, "tool_prefix.md")
if os.path.exists(_TOOL_PREFIX_PATH):
    with open(_TOOL_PREFIX_PATH, "r", encoding="utf-8") as _f:
        _TOOL_PREFIX = _f.read().strip() + "\n\n"
else:
    _TOOL_PREFIX = ""


# 全局变量，在 app.py 启动时通过 init_tools() 赋值
_vectordb = None
_all_chunks = []
_llm = None
_reranker = None


def init_tools(vectordb, all_chunks, llm=None, reranker=None):
    """启动时注入向量库、文档块、LLM 和 Reranker"""
    global _vectordb, _all_chunks, _llm, _reranker
    _vectordb = vectordb
    _all_chunks = all_chunks
    if llm is not None:
        _llm = llm
    if reranker is not None:
        _reranker = reranker


def _rewrite_query(query: str) -> str:
    """短查询（≤10字）自动扩展为完整句子，提高检索命中率"""
    if _llm is None or len(query) > 10:
        return query
    prompt = f"""请将下面的短查询改写成一个完整的疑问句，用于文档搜索。
要求：直接返回改写后的句子，不要解释，不要添加原查询没有的信息，用中文。

原始查询：{query}
改写后："""
    try:
        resp = _llm.invoke(prompt)
        expanded = resp.content.strip().strip('"').strip("'").strip("「」")
        if expanded:
            logger.info(f"[{trace_id_var.get()}] 查询改写: '{query}' → '{expanded}'")
            return expanded
    except Exception:
        pass
    return query


@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    try:
        url = f"https://wttr.in/{city}?format=%C+%t"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
        return "获取天气失败"
    except:
        return "获取天气失败"


@tool
def search_docs(query: str) -> str:
    """搜索本地知识库中的文档内容。当用户的问题涉及知识库中的文档时，必须调用此工具。
    例如：询问某个文件的内容、技术概念、对比分析等，都先用此工具搜索。"""
    if _vectordb is None or not _all_chunks:
        return "知识库尚未初始化，请先上传文档"

    # 短查询自动扩展，提高检索命中率
    expanded = _rewrite_query(query)
    logger.info(f"[{trace_id_var.get()}] hybrid_search 查询: '{expanded}'")
    results = hybrid_search(expanded, _vectordb, _all_chunks, top_k=6, reranker=_reranker)
    logger.info(f"[{trace_id_var.get()}] hybrid_search 返回 {len(results)} 条结果")
    if not results:
        return "未找到相关文档"

    # 分数阈值：最高分低于 0.3 则认为检索不相关，拒绝回答
    best_score = results[0][1]
    if best_score < 0.3:
        return "未找到相关文档"

    formatted = []
    for content, score, source in results:
        fname = os.path.basename(source) if source else "未知来源"
        logger.info(f"[{trace_id_var.get()}]   → {fname}（相似度：{score:.2f}）")
        formatted.append(f"【来源：{fname}】（相似度：{score:.2f}）\n{content}")
    return (
        _TOOL_PREFIX
        + "\n\n".join(formatted)
    )
@tool
def review_result(passed: bool, score: int, issues: list[str], feedback: str) -> str:
    """审查答案质量。判断是否符合标准。"""
    return json.dumps({"passed": passed, "score": score, "issues": issues, "feedback": feedback})

