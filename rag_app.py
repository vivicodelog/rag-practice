# 先是导入安装的依赖和包
import os
import json
import hashlib
import requests
from dotenv import load_dotenv
import gradio as gr
from datetime import datetime
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain.agents import create_agent

load_dotenv()

SYNC_STATE_FILE = "./chroma_db/sync_state.json"

class BaseSource:
    def get_documents(self):
        raise NotImplementedError()
    def get_sync_key(self):
        raise NotImplementedError()
    
class FileSource(BaseSource):
    def __init__(self, paths):
        self.paths = paths

    def get_documents(self):
        docs = []
        for path,fmt in self.paths:
            if not os.path.exists(path):
                continue
            loader = TextLoader(path, encoding="utf-8") if fmt == "txt" else PyPDFLoader(path)
            loaded = loader.load()
            for doc in loaded:
                doc_id = os.path.basename(path) + "::" + doc.page_content[:50]
                docs.append((doc_id,doc.page_content,{"source": path}))
            print(f"{path}加载成功")
        return docs 
    
    def get_sync_key(self):
        combined = ""
        for path,_ in self.paths:
            if os.path.exists(path):
                with open(path,"rb") as f:
                    combined += hashlib.md5(f.read()).hexdigest()
        return hashlib.md5(combined.encode()).hexdigest()
    

class DatabaseSource(BaseSource):
    def __init__(self,connection_string,query):
        self.connection_string = connection_string
        self.query = query
    def get_documents(self):
        raise NotImplementedError
    
    def get_sync_key(self):
        raise NotImplementedError   
    
def build_vectorstore(source,embeddings,persist_dir):
    """基于数据库构建向量库"""
    print("加载文档...")
    raw_docs = source.get_documents()
    if not raw_docs:
        raise Exception("没有找到任何文档")
    print("切分文档...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size = 300,chunk_overlap = 30)
    all_chunks = []
    for doc_id,text,meta in raw_docs:
        chunks = text_splitter.split_text(text)
        for i,chunk in enumerate(chunks):
            all_chunks.append((f"{doc_id}::chunks{i}", chunk,{**meta,"doc_id":doc_id}))
    print(f"  切分为 {len(all_chunks)} 个片段")

    docs = [Document(page_content = c,metadata = m) for _,c,m in all_chunks]
    vectordb = Chroma.from_documents(
        documents = docs,
        embedding = embeddings,
        persist_directory=persist_dir,
    )

    # 保存 chunks 到 JSON，供关键词回退搜索使用
    chunks_path = os.path.join(persist_dir, "chunks.json")
    json.dump([{"content": d.page_content, "metadata": d.metadata} for d in docs],
              open(chunks_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("向量数据库构建完成")
    return vectordb

# 使用从 ModelScope 下载的本地模型（国内网络无需翻墙）
embeddings = HuggingFaceEmbeddings(
    model_name="./modelscope_cache/models/BAAI/bge-small-zh-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

def vectordb_from_existing():
    if os.path.exists("./chroma_db/chroma.sqlite3"):
        return Chroma(
            embedding_function=embeddings,
            persist_directory="./chroma_db",
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

source = FileSource([
    ("data/test.txt","txt"),
    ("data/dictionary.pdf","pdf")
])

should_rebuild, vectordb = need_rebuild(source, SYNC_STATE_FILE)


if should_rebuild or vectordb is None:
    vectordb = build_vectorstore(source,embeddings,"./chroma_db")
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    json.dump({"sync_key": source.get_sync_key(), "updated_at": datetime.now().isoformat()}, open(SYNC_STATE_FILE, "w"))
else:
    print("现有的向量库")

print("正在初始化")

llm = ChatDeepSeek(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    model="deepseek-chat",
    temperature=0.7
)

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

retriever = vectordb.as_retriever(search_kwargs={"k": 6})

# 加载所有 chunks 用于关键词回退搜索
_all_chunks = []
chunks_json = os.path.join("./chroma_db", "chunks.json")
if os.path.exists(chunks_json):
    try:
        _all_chunks = json.load(open(chunks_json, encoding="utf-8"))
        print(f"  关键词回退搜索已加载（{len(_all_chunks)} 个文档）")
    except Exception as e:
        print(f"  关键词搜索加载失败: {e}")

@tool
def search_docs(query: str) -> str:
    """搜索本地知识库中的文档内容。当需要查找具体信息时调用此工具，传入搜索关键词。"""
    # 1. 向量检索（语义匹配）
    docs = retriever.invoke(query)

    # 2. 关键词回退搜索：用 jieba 分词提取关键词，补全向量搜索遗漏的内容
    if _all_chunks:
        try:
            import jieba
            import re
            # 用 jieba 分词提取有意义的词（过滤通用词）
            stop_words = {'问题', '什么', '怎么', '解决', '方案', '方法', '如何'}
            words = [w for w in jieba.lcut(query) if len(w) >= 2 and w not in stop_words]
            # 如果 jieba 没提取到词（如纯英文查询），用正则提取英文/数字词
            if not words:
                words = re.findall(r'[a-zA-Z0-9_]{2,}', query)
        except:
            words = []

        # 对每个 chunk 计算关键词匹配得分
        kw_set = set(words)
        scored = []
        for item in _all_chunks:
            content = item["content"] if isinstance(item, dict) else item.page_content
            score = sum(len(kw) for kw in kw_set if kw in content)
            if score > 0:
                scored.append((score, content, item.get("metadata", {})))

        # 关键词结果按得分排序 + 向量结果补充（去重）
        scored.sort(key=lambda x: -x[0])
        seen = set()
        kw_docs = [Document(page_content=c, metadata=m) for _, c, m in scored]
        for d in kw_docs:
            seen.add(d.page_content)
        for d in docs:
            if d.page_content not in seen:
                kw_docs.append(d)
        docs = kw_docs

    return "\n\n".join(doc.page_content for doc in docs[:6])

tools = [get_weather, search_docs]

system_prompt = """你是一个问答助手。
- 如果用户的问题在本地知识库中可能有答案，先用 search_docs 工具搜索
- 如果用户询问天气等实时信息，用 get_weather 工具
- 如果知识库和工具都没有答案，请说不知道"""

agent = create_agent(llm, tools, system_prompt=system_prompt)

def rag_with_tools(question):
    """流式 RAG：逐步骤输出，最后返回完整回答"""
    for event in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        last_msg = event["messages"][-1]
        if hasattr(last_msg, "content") and last_msg.content:
            yield last_msg.content

def chat_with_rag(message, history):
    if not message:
        yield ""
        return
    try:
        response = ""
        for chunk in rag_with_tools(message):
            response = chunk
            yield response
    except Exception as e:
        yield f"出错了：{e}"

demo = gr.ChatInterface(
    fn=chat_with_rag,
    title="📚 RAG 智能问答 (LangChain 版)",
    description="基于 LangChain + DeepSeek + Chroma 的文档问答助手",
)
if __name__ == "__main__":
    demo.launch(share=False)    
