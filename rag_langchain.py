import os
import json
import hashlib
import requests
from dotenv import load_dotenv
import gradio as gr
from datetime import datetime
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

load_dotenv()

SYNC_STATE_FILE = "./chroma_langchain/sync_state.json"


# ==================== 文档源抽象层 ====================
# 新增一个源：继承 BaseSource，实现 get_documents() 即可
class BaseSource:
    """文档源基类。所有文档源（文件、数据库等）都实现这个接口"""
    def get_documents(self):
        """返回 [(doc_id, text, metadata), ...]"""
        raise NotImplementedError

    def get_sync_key(self):
        """返回当前源的"版本标记"（文件用 hash，数据库用时间戳）"""
        raise NotImplementedError


class FileSource(BaseSource):
    """从文件读取文档"""
    def __init__(self, paths):
        self.paths = paths  # [("data/test.txt", "txt"), ("data/dictionary.pdf", "pdf")]

    def get_documents(self):
        docs = []
        for path, fmt in self.paths:
            if not os.path.exists(path):
                continue
            loader = TextLoader(path, encoding="utf-8") if fmt == "txt" else PyPDFLoader(path)
            loaded = loader.load()
            for doc in loaded:
                doc_id = os.path.basename(path) + "::" + doc.page_content[:50]
                docs.append((doc_id, doc.page_content, {"source": path}))
            print(f"  OK - {path} 加载成功")
        return docs

    def get_sync_key(self):
        """所有文件的内容 hash 拼接作为版本标记"""
        combined = ""
        for path, _ in self.paths:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    combined += hashlib.md5(f.read()).hexdigest()
        return hashlib.md5(combined.encode()).hexdigest()


class DatabaseSource(BaseSource):
    """从数据库读取文档（以后接入用）"""
    def __init__(self, connection_string, query):
        self.connection_string = connection_string
        self.query = query

    def get_documents(self):
        # TODO: 连接数据库执行 self.query，返回文档列表
        # 格式：[(row.id, row.content, {"source": "db", "updated_at": str(row.updated_at)}), ...]
        raise NotImplementedError("数据库源还没实现，后面再加")

    def get_sync_key(self):
        # 数据库用 max(updated_at) 作为版本标记
        # TODO: select max(updated_at) from ...
        raise NotImplementedError("数据库源还没实现，后面再加")


# ==================== 向量库同步引擎 ====================
def build_vectorstore(source, embeddings, persist_dir):
    """统一的向量库构建入口：切分 → 嵌入 → 存储"""
    print("加载文档...")
    raw_docs = source.get_documents()
    if not raw_docs:
        raise Exception("没有找到任何文档")

    print("切分文档...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    all_chunks = []
    for doc_id, text, meta in raw_docs:
        chunks = text_splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append((f"{doc_id}::chunk{i}", chunk, {**meta, "doc_id": doc_id}))

    print(f"  切分为 {len(all_chunks)} 个片段")

    print("构建向量库...")
    docs = [Document(page_content=c, metadata=m) for _, c, m in all_chunks]
    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    print(f"  OK - 向量库创建完成，共 {vectordb._collection.count()} 条记录")
    return vectordb


embeddings = OpenAIEmbeddings(
    model="BAAI/bge-large-zh-v1.5",
    api_key=os.getenv("SILICON_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
    embedding_ctx_length=512,
    chunk_size=16,
)

# ==================== 向量库同步引擎 ====================
def vectordb_from_existing():
    """如果向量库已存在，直接加载"""
    if os.path.exists("./chroma_langchain/chroma.sqlite3"):
        return Chroma(
            embedding_function=embeddings,
            persist_directory="./chroma_langchain",
        )
    return None

def need_rebuild(source, state_file):
    """检查源是否变了，需要重建向量库"""
    current_key = source.get_sync_key()
    old_state = {}
    if os.path.exists(state_file):
        old_state = json.load(open(state_file))
    if old_state.get("sync_key") == current_key:
        print("  文档无变化，跳过重建")
        return False, vectordb_from_existing()
    print("  检测到文档变化，重建向量库...")
    return True, None

# 当前用文件源，后续换成 DatabaseSource 即可
source = FileSource([
    ("data/test.txt", "txt"),
    ("data/dictionary.pdf", "pdf"),
])

should_rebuild, vectordb = need_rebuild(source, SYNC_STATE_FILE)

if should_rebuild or vectordb is None:
    vectordb = build_vectorstore(source, embeddings, "./chroma_langchain")
    # 记录当前源的版本标记
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    json.dump({"sync_key": source.get_sync_key(), "updated_at": str(datetime.now())},
              open(SYNC_STATE_FILE, "w"))
else:
    print(f"  OK - 加载现有向量库，共 {vectordb._collection.count()} 条记录")

# ==================== 4. 创建检索链 ====================
print("初始化 DeepSeek...")
llm = ChatDeepSeek(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    model="deepseek-chat",
    temperature=0.7
)
# ==================== 2. 天气工具 ====================
def get_weather(city):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
        return "获取天气失败"
    except:
        return "获取天气失败"

# ==================== 3. 工具定义 ====================
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，例如：北京、上海"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

# 绑定工具到模型（让模型知道它可以调用哪些工具）
llm_with_tools = llm.bind_tools(tools)

# 工具名称 → 实际 Python 函数的映射表（工具调用的种类，需要把可能有调用的工具都放在这里）
available_functions = {
    "get_weather": get_weather,
}

retriever = vectordb.as_retriever(search_kwargs={"k": 3})

# 构建问答链（LCEL 模式）
prompt_template = ChatPromptTemplate.from_template("""你是一个问答助手，可以基于提供的上下文回答问题。如果上下文中没有相关信息，请说不知道。
但注意：如果用户需要查询天气等实时信息，你有可用的工具，不用局限于上下文，可以用内部知识，但是先读取文档的内容或者上下文内容找答案。

上下文：
{context}

问题：
{question}

回答：""")

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def rag_with_tools(question):
    """RAG + 工具调用的主流程：检索 → LLM(可调工具) → 最终回答"""
    # Step 1: RAG 检索，拿到文档上下文
    context = format_docs(retriever.invoke(question))

    # Step 2: 构造消息，调用带工具的模型
    messages = prompt_template.format_messages(context=context, question=question)
    response = llm_with_tools.invoke(messages)

    # Step 3: 模型是否决定调用工具？（tool_calls 不为空 = 模型要调工具）
    if response.tool_calls:
        print(f" 模型调用了工具: {[t['name'] for t in response.tool_calls]}")
        messages.append(response)  # 把模型的工具调用请求加入历史

        # 逐个执行工具
        for tool_call in response.tool_calls:
            func = available_functions[tool_call["name"].lower()]
            result = func(**tool_call["args"])
            print(f"  🔧 {tool_call['name']}({tool_call['args']}) = {result}")
            messages.append({
                "role": "tool",
                "content": str(result),
                "tool_call_id": tool_call["id"],
            })

        # Step 4: 带着工具结果，让模型生成最终回答（不用 bind_tools，直接文本输出）
        response = llm.invoke(messages)

    return response.content


print("一切就绪！")

# ==================== 5. 问答函数 ====================
def chat_with_rag(message, history):
    """Gradio 调用的函数"""
    if not message:
        return ""

    try:
        return rag_with_tools(message)
    except Exception as e:
        return f"出错了：{e}"

# ==================== 6. Gradio 界面 ====================
demo = gr.ChatInterface(
    fn=chat_with_rag,
    title="RAG 智能问答 (LangChain 版)",
    description="基于 LangChain + DeepSeek + Chroma 的文档问答助手"
)

if __name__ == "__main__":
    demo.launch(share=False)