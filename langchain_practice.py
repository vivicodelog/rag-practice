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
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

load_dotenv()

SYNC_STATE_FILE = "./chroma_langchain/sync_state.json"

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
            loader = Textloader(path,encoding= "utf-8") if fmt == "txt" else PyPDFLoader(path)
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
    
    print("向量数据库构建完成")
    return vectordb

embeddings = OpenAIEmbeddings(
    model = "BAAO/bge-large-zh-v1.5",
    api_key=os.getenv("SILICON_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
    embedding_ctx_length=512,
    chunk_size=16,
)

def vectordb_from_existing():
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

source = FileSource([
    ("data/test.txt","txt"),
    ("data/dictionary.pdf","pdf")
])

should_rebuild, vectordb = need_rebuild(source, SYNC_STATE_FILE)


if should_rebuild or vectordb is None:
    vectordb = build_vectorstore(source,embeddings,"./chroma_langchain")
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    json.dump({"sync_key": source.get_sync_key(),"updated_at": datetime.now()},open({"SYNC_STATE_FILE","w"}))
else:
    print("现有的向量库")

print("正在初始化")

llm = ChatDeepSeek(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    model="deepseek-chat",
    temperature=0.7
)

def get_weather(city):
    try: 
        url = f"https://wttr.in/{city}?format=%C+%t"
        response = requests.get(url, timeout=5)
        if response.status_code == 200: 
            return response.text.strip()
        return "获取天气失败"
    except:
        return "获取天气失败"

tools =[
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    }
                },
                "required": ["city"]
            }
        }
    }
]
llm_with_tools = llm.bind_tools(tools)

available_functions = {
    "get_weather": get_weather,
}

retriever = vectordb.as_retriever(search_kwargs={"k": 3})

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
    context = format_docs(retriever.invoke(question))
    messages = prompt_template.format_messages(context=context, question=question)
    response = llm_with_tools.invoke(messages)

    if response.tool_calls:
        print(f" 模型调用了工具: {[t['name'] for t in response.tool_calls]}")
        messages.append(response)
        for tool_call in response.tool_calls:
            func = available_functions[tool_call["name"].lower()]
            result = func(**tool_call["args"])
            messages.append({
                "role": "tool",
                "content": str(result),
                "tool_call_id": tool_call["id"],
            })
        response = llm.invoke(messages)
    return response.content

def chat_with_rag(message, history):
    if not message:
        return ""   
    try:
        return rag_with_tools(message)
    except Exception as e:
        return f"出错了：{e}"

demo = gr.ChatInterface(
    fn=chat_with_rag,
    title="📚 RAG 智能问答 (LangChain 版)",
    description="基于 LangChain + DeepSeek + Chroma 的文档问答助手",
)
if __name__ == "__main__":
    demo.launch(share=False)    
