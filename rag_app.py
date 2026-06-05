# 先是导入安装的依赖和包
import os
import json
import hashlib
import requests
from dotenv import load_dotenv
import gradio as gr
from datetime import datetime
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader, UnstructuredMarkdownLoader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain.agents import create_agent

load_dotenv()
# 同步状态文件，用于记录向量数据库的同步进度
SYNC_STATE_FILE = "./chroma_db/sync_state.json"
# 数据目录，存放原始文档的位置，系统从这个目录读取原始文件进行处理
DATA_DIR = "data"
# 文档清单文件，完整路径为 data/manifest.json，记录 data/ 目录中所有文档的元数据，作为文档的索引清单，快速获取文档列表，无需重复扫描目录
MANIFEST_FILE = os.path.join(DATA_DIR, "manifest.json")
# 文档处理流程：

# 1. 用户上传文件 → 保存到 DATA_DIR (data/ 目录)

# 2. 更新 MANIFEST_FILE (data/manifest.json)
#    - 记录文件信息

# 3. 同步到向量数据库 → 更新 SYNC_STATE_FILE (chroma_db/sync_state.json)
#    - 记录同步状态
#    - 避免重复处理

# ==================== 文档清单系统 ====================
# 打开 manifest.json 这个文件（用"只读"方式）
# 用 UTF-8 编码读取（支持中文）
# 把这个文件叫做 f（代号）
# 用 json.load(f) 读取文件里的 JSON 内容
# 返回读到的内容
# 自动关闭文件（这是 with 的功劳）
def load_manifest():
    """读取文档清单"""
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:#有with就相当于后面自动关闭文件
            return json.load(f)
    return []


# json.dump() = 把 Python 对象转换成 JSON 格式并写入文件
# manifest = 要保存的清单数据
# f = 写入到这个文件
# ensure_ascii=False = 中文正常显示（不转成 \uxxxx）
# indent=2 = 缩进2个空格，让文件好看易读
def save_manifest(manifest):
    """保存文档清单"""
    os.makedirs(DATA_DIR, exist_ok=True)#创建文件夹，如果没有就创建，否则不用，也不报错
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)#json.dump() = 把 Python 对象转换成 JSON 格式并写入文件


def sync_manifest():
    """同步 manifest 与实际文件系统，确保清单始终反映 data/ 目录的真实状态

    之前的 initialize_manifest() 只在首次运行时扫描目录，
    之后如果外部修改文件，manifest 就过时了。
    这个版本每次调用都会比对文件系统，做三个事情：
    1. 新增的文档 → 自动加入清单
    2. 被删除的文档 → 从清单移除
    3. 已有文档的元数据（大小、修改时间）→ 更新
    """
    # 扫描当前文件系统，收集实际存在的文件
    current_files = {}#current_files = 硬盘上真实存在的文件
    for fname in sorted(os.listdir(DATA_DIR)):
        ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''#取出文件的扩展名（比如 .pdf 就取出 pdf），转成小写方便比较
        if ext not in ('txt', 'pdf', 'docx', 'md', 'markdown'):
            continue
        path = os.path.join(DATA_DIR, fname)#拼接出文件的完整路径，比如 data/报告.pdf
        if os.path.isfile(path):# # 检查是不是文件（不是文件夹）
            current_files[fname] = {
                "size": os.path.getsize(path),# 文档大小
                "mtime": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()# 最后修改时间
            }

    # 加载已有 manifest
    manifest = load_manifest()
    existing_map = {item["filename"]: item for item in manifest}#字典推导式，把列表转成字典

    new_manifest = []
    for fname, info in current_files.items():
        if fname in existing_map:
            # 已有记录 → 更新大小和修改时间（文件可能被外部修改过）
            existing_map[fname]["size"] = info["size"]
            existing_map[fname]["upload_date"] = info["mtime"]
            new_manifest.append(existing_map[fname])
        else:
            # 新文件 → 新增记录
            new_manifest.append({
                "filename": fname,
                "size": info["size"],
                "upload_date": info["mtime"]
            })

    save_manifest(new_manifest)
    return new_manifest


# ==================== 文档源抽象层 ====================
class BaseSource:
    def get_documents(self):
        raise NotImplementedError()#抛出"未实现错误"，没有警告的说明书----python的写法
    def get_sync_key(self):
        raise NotImplementedError()#抛出"未实现错误"


class FileSource(BaseSource):#FileSource 是 BaseSource 的一个具体实现，专门从本地文件夹读取文档，并能智能检测文件变化
    def __init__(self, directory):
        self.directory = directory#告诉这个文件源要去哪个文件夹找文档

    def get_documents(self):#加载所有文档内容和元数据，返回文档列表-------------------------获取文档用于向量化
        docs = []#存放的所有文档a
        for fname in os.listdir(self.directory):
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if ext not in ('txt', 'pdf', 'docx', 'md'):
                continue
            path = os.path.join(self.directory, fname)#获取完整路径把文件夹路径和文件名拼接到一起，形成完整的文件路径
            if not os.path.isfile(path):
                continue
            if ext == "txt":
                loader = TextLoader(path, encoding="utf-8")
            elif ext == "pdf":
                loader = PyPDFLoader(path)
            elif ext == "docx":
                loader = Docx2txtLoader(path)
            elif ext in ("md", "markdown"):
                loader = UnstructuredMarkdownLoader(path)
            else:
                continue  # 不支持的格式跳过
            loaded = loader.load()#加载文档内容，加载文档块
            for doc in loaded:
                doc_id = fname + "::" + doc.page_content[:50]
                docs.append((doc_id, doc.page_content, {"source": path}))
            print(f"  {fname} 加载成功")
        return docs

    def get_sync_key(self):#计算整个文件夹的"指纹"，返回MD5字符串------------------用途 快速检测变化
        combined = ""
        for fname in sorted(os.listdir(self.directory)):
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if ext not in ('txt', 'pdf', 'docx', 'md'):
                continue
            path = os.path.join(self.directory, fname)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    combined += hashlib.md5(f.read()).hexdigest()
        return hashlib.md5(combined.encode()).hexdigest()#双层的加密


class DatabaseSource(BaseSource):
    def __init__(self, connection_string, query):
        self.connection_string = connection_string
        self.query = query
    def get_documents(self):
        raise NotImplementedError
    def get_sync_key(self):
        raise NotImplementedError


# ==================== 向量库构建 ====================
def build_vectorstore(source, embeddings, persist_dir):#参数（文档来源、嵌入模型（把文字转成数字向量的工具）、向量库保存目录）
    print("加载文档...")
    raw_docs = source.get_documents()#获取所有文档
    if not raw_docs:
        raise Exception("没有找到任何文档")
    print("切分文档...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    all_chunks = []
    for doc_id, text, meta in raw_docs:#参数（doc_id = "报告.pdf::报告内容前50字..."、text = "完整的报告内容..."、meta = {"source": "报告.pdf"}）
        chunks = text_splitter.split_text(text)
        for i, chunk in enumerate(chunks):#enumerate() 的作用： 同时获取索引和值
            all_chunks.append((f"{doc_id}::chunks{i}", chunk, {**meta, "doc_id": doc_id}))
            #追溯到原始文档，每个块都有唯一ID，知道是文档的第几个块     
                                                            # {**meta, "doc_id": doc_id} 是字典解包语法  
                                                            # # 传统写法（冗长）
                                                            # new_meta = {}
                                                            # new_meta.update(meta)
                                                            # new_meta["doc_id"] = doc_i
    print(f"  切分为 {len(all_chunks)} 个片段")

    docs = [Document(page_content=c, metadata=m) for _, c, m in all_chunks]#Document 是LangChain 框架的标准文档格式，包含：内容（page_content）+ 元数据（metadata）
    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir,
    )#Chroma.from_documents 把每个文档块传给嵌入模型,嵌入模型把文字转成向量（一串数字，比如 384维）,把向量存储到 Chroma 数据库

    # 保存 chunks 到 JSON，供关键词回退搜索使用
    chunks_path = os.path.join(persist_dir, "chunks.json")#把 chunks.json 把目录和文件名拼接成完整的路径,例如.\chroma_db\chunks.json
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump([{"content": d.page_content, "metadata": d.metadata} for d in docs],
                  f, ensure_ascii=False, indent=2)
#                  打开文件（写模式）                     中文正常显示        缩进2个空格
    print("向量数据库构建完成")
    return vectordb


# ==================== 向量库重建（封装成函数，供上传/删除后调用）====================
def rebuild_vectorstore():
    """重建向量库并更新全局变量"""
    global source, vectordb, retriever, _all_chunks
    sync_manifest()  # 先同步 manifest，确保文档列表和文件系统一致
    source = FileSource(DATA_DIR)
    vectordb = build_vectorstore(source, embeddings, "./chroma_db")
    retriever = vectordb.as_retriever(search_kwargs={"k": 6})

    chunks_path = os.path.join("./chroma_db", "chunks.json")#把目录和文件名拼接成完整的路径
    if os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            _all_chunks = json.load(f)
    else:
        _all_chunks = []
# 加载 chunks           从文件路径里取出目录部分
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)#创建这个目录，有了也不报错
    with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "sync_key": source.get_sync_key(),
            "updated_at": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    print("向量库重建完成")


# 使用从 ModelScope 下载的本地嵌入模型
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


def need_rebuild(source, state_file):#source - 文档源对象（能计算指纹）state_file - 状态文件路径（如 "./chroma_db/sync_state.json"）
    current_key = source.get_sync_key()
    old_state = {}
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            old_state = json.load(f)
    if old_state.get("sync_key") == current_key:
        print("  文档无变化，跳过重建")
        return False, vectordb_from_existing()
    print("  检测到文档变化，重建向量库...")
    return True, None
# ① 首次运行 → need_rebuild 返回 (True, None)
#    if True or True → 重建 ✅

# ② 文件没变 + 向量库还在 → (False, <Chroma对象>)
#    if False or False → 跳过 ✅

# ③ 文件变了 → (True, None)
#    if True or True → 重建 ✅

# ④ 文件没变 + 向量库被删了 → (False, None)
#    if False or True → 重建 ✅（兜住）

# ==================== 初始化 ====================
os.makedirs(DATA_DIR, exist_ok=True)
sync_manifest()

source = FileSource(DATA_DIR)#创建一个"文件源"对象

##  should_rebuild = False
#  vectordb       = 向量库
should_rebuild, vectordb = need_rebuild(source, SYNC_STATE_FILE)

if should_rebuild or vectordb is None:
    vectordb = build_vectorstore(source, embeddings, "./chroma_db")
    os.makedirs(os.path.dirname(SYNC_STATE_FILE), exist_ok=True)
    with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"sync_key": source.get_sync_key(), "updated_at": datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)
else:
    print("使用现有的向量库")

print("正在初始化 LLM...")

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

#           把向量数据库转换成检索器
retriever = vectordb.as_retriever(search_kwargs={"k": 6})

# 加载所有 chunks 用于关键词回退搜索------向量库有问题时，json文件兜底的地方
_all_chunks = []
chunks_json = os.path.join("./chroma_db", "chunks.json")
if os.path.exists(chunks_json):
    try:
        with open(chunks_json, "r", encoding="utf-8") as f:
            _all_chunks = json.load(f)
        print(f"  关键词回退搜索已加载（{len(_all_chunks)} 个文档）")
    except Exception as e:
        print(f"  关键词搜索加载失败: {e}")


@tool
def search_docs(query: str) -> str:
    """搜索本地知识库中的文档内容。当需要查找具体信息时调用此工具，传入搜索关键词。"""
    docs = retriever.invoke(query)

    if _all_chunks:
        try:
            import jieba
            import re
            stop_words = {'问题', '什么', '怎么', '解决', '方案', '方法', '如何'}
            words = [w for w in jieba.lcut(query) if len(w) >= 2 and w not in stop_words]
            if not words:
                words = re.findall(r'[a-zA-Z0-9_]{2,}', query)
        except:
            words = []

        kw_set = set(words)
        scored = []
        for item in _all_chunks:
            content = item["content"] if isinstance(item, dict) else item.page_content
            score = sum(len(kw) for kw in kw_set if kw in content)
            if score > 0:
                scored.append((score, content, item.get("metadata", {})))

        scored.sort(key=lambda x: -x[0])
        seen = set()
        kw_docs = [Document(page_content=c, metadata=m) for _, c, m in scored]
        for d in kw_docs:
            seen.add(d.page_content)
        for d in docs:
            if d.page_content not in seen:
                kw_docs.append(d)
        docs = kw_docs
    # === 后续优化方向：统一排序 ===
    # 目前是"关键词结果排前面，向量结果补后面"，
    # 对模糊搜索（如"人工智能的应用"）不太公平——
    # 向量库认为最相关的可能被关键词结果挤到后面。
    #(先合并、再统一排序,但是需要向量库返回一下score,这个需要配置返回值)
    ## 优化思路：
    # 1. 关键词匹配 → 算一个 0~1 的得分（命中字数 / 总字数）
    # 2. 向量库结果 → 取相似度分数（retriever 可以返回 score）
    # 3. 两边归一化后统一排序，不分先后
    # 这样第一条就是"综合最相关"的，而不是"关键词最多的"
    # 把结果格式化：在每个段落前标明来源文档
    formatted = []
    for doc in docs[:6]:
        source = doc.metadata.get("source", "")
        fname = os.path.basename(source) if source else "未知来源"
        formatted.append(f"【来源：{fname}】\n{doc.page_content}")
    return "\n\n".join(formatted)


tools = [get_weather, search_docs]

system_prompt = """你是一个问答助手。
- 如果用户的问题在本地知识库中可能有答案，先用 search_docs 工具搜索
- 如果用户询问天气等实时信息，用 get_weather 工具
- 如果知识库和工具都没有答案，请说不知道
- 回答时请说明信息来源（例如：根据【xxx.txt】中的内容，...）"""

agent = create_agent(llm, tools, system_prompt=system_prompt)


# ==================== 文档管理业务函数 ====================
def get_document_df():
    """返回文档列表（供 Dataframe 组件渲染）"""
    manifest = load_manifest()
    if not manifest:
        return [["暂无文档", "", ""]]
    rows = []
    for item in manifest:
        size_kb = item["size"] / 1024
        rows.append([
            item["filename"],
            f"{size_kb:.1f} KB",
            item["upload_date"][:19]
        ])
    return rows


def get_delete_choices():
    """返回文件名列表（供 Dropdown 组件使用）"""
    manifest = load_manifest()
    return [item["filename"] for item in manifest]


def update_delete_dropdown():
    """刷新下拉框，清空选中值"""
    choices = get_delete_choices()
    return gr.Dropdown(choices=choices, value=None, interactive=True)


def upload_document(file):
    """保存文件 → 更新清单 → 重建向量库"""
    drop = update_delete_dropdown  # 简短别名，后面每处都要用
    try:
        # Gradio 不同版本传文件的方式不同，统一处理
        if file is None:
            return "请选择文件", get_document_df(), drop()
        # 某些 Gradio 版本会把单文件包在列表里
        if isinstance(file, (list, tuple)):
            file = file[0] if file else None
        if file is None:
            return "请选择文件", get_document_df(), drop()

        # Gradio 6 的 UploadButton 传的是文件路径字符串，不是 FileData 对象
        if isinstance(file, str):
            file_path = file
            original_name = os.path.basename(file)
        else:
            file_path = file.path
            original_name = file.orig_name or os.path.basename(file_path)

        filename = original_name
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('txt', 'pdf', 'docx', 'md',"doc"):
            return "仅支持 TXT 和 PDF 文件", get_document_df(), drop()

        manifest = load_manifest()
        if any(item["filename"] == filename for item in manifest):
            return f"文件 '{filename}' 已存在，请先删除旧文件", get_document_df(), drop()

        dest_path = os.path.join(DATA_DIR, filename)
        with open(file_path, "rb") as src, open(dest_path, "wb") as dst:
            dst.write(src.read())

        manifest.append({
            "filename": filename,
            "size": os.path.getsize(dest_path),
            "upload_date": datetime.now().isoformat()
        })
        save_manifest(manifest)

        try:
            rebuild_vectorstore()
            get_document_df()
        except Exception as e:
            # 重建失败 → 回滚：删掉已保存的文件和 manifest 记录
            if os.path.exists(dest_path):
                os.remove(dest_path)
            manifest = load_manifest()
            manifest = [item for item in manifest if item["filename"] != filename]
            save_manifest(manifest)
            raise  # 重新抛出，让外层 except 捕获

        return f"✓ 文件 '{filename}' 上传成功，向量库已重建", get_document_df(), drop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ 上传失败：{type(e).__name__}: {e}", get_document_df(), drop()


def delete_document(filename):
    """删除文件 → 更新清单 → 重建向量库"""
    drop = update_delete_dropdown
    try:
        if not filename:
            return get_document_df(), drop(), "请选择要删除的文件"

        manifest = load_manifest()
        manifest = [item for item in manifest if item["filename"] != filename]
        save_manifest(manifest)

        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        rebuild_vectorstore()

        return get_document_df(), drop(), f"✓ 文件 '{filename}' 已删除，向量库已重建"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return get_document_df(), drop(), f"❌ 删除失败：{type(e).__name__}: {e}"


def refresh_list():
    return get_document_df()


# ==================== 聊天函数（供 ChatInterface 调用）====================
def chat_fn(message, history):
    """ChatInterface 的回调函数。
    message: 用户输入的字符串
    history: list[dict]，格式为 [{"role": "user/assistant", "content": "..."}]
    yield: 流式返回回答文本"""
    MAX_ROUNDS = 4

    if len(history) > MAX_ROUNDS:
        old = history[:-MAX_ROUNDS]#旧的部分（需要压缩） # 从头开始到 end（不包含 end）
        recent = history[-MAX_ROUNDS:]#新的部分（需要保留）# 最后 n 个元素
                                                        #list[start:end]  # start 开始索引（包含），end 结束索引（不包含）
                                                        # list[:end]       # 从头开始到 end（不包含 end）
                                                        # list[start:]     # 从 start 开始到结尾
                                                        # list[-n:]        # 最后 n 个元素
                                                        # list[:-n]        # 除了最后 n 个元素之外的所有元素
        summary_prompt = "请将以下对话压缩为一句简短摘要：\n"
        for msg in old:
            if msg["role"] == "user":
                summary_prompt += f"问：{msg['content']}\n"
            else:
                summary_prompt += f"答：{msg['content']}\n"
        summary = llm.invoke(summary_prompt).content

        messages = [{"role": "system", "content": f"之前的对话摘要：{summary}"}]
        for msg in recent:
            messages.append({"role": msg["role"], "content": msg["content"]})
    else:
        messages = []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    for event in agent.stream(
        {"messages": messages},
        stream_mode="values",#返回完整的事件值
    ):#流式调用 AI 代理
        last_msg = event["messages"][-1]#获取最新消息
        msg_type = getattr(last_msg, "type", "")
        if msg_type in ("human", "tool"):
            continue
        if msg_type == "ai" and getattr(last_msg, "tool_calls", None):
            continue## AI 在调用工具，不是最终回答
        if hasattr(last_msg, "content") and last_msg.content:
            yield last_msg.content#yield - 生成器，逐步输出内容


# ==================== 构建 UI ====================
CUSTOM_CSS = """
footer {display: none !important;}
.gradio-container {max-width: 900px !important; margin: 0 auto;}
"""

with gr.Blocks(title="RAG 智能问答") as demo:
    # ---------- Tab 1: 问答 ----------
    with gr.Tab("💬 问答"):
        # 直接用 ChatInterface，自动管理消息格式（Gradio 6 原生支持）
        gr.ChatInterface(
            fn=chat_fn,
            title="📚 RAG 智能问答",
            description="基于 LangChain + DeepSeek + Chroma 的文档问答助手",
        )

    # ---------- Tab 2: 文档管理 ----------
    with gr.Tab("📁 文档管理"):
        gr.Markdown("## 📤 上传文档")
        gr.Markdown("支持 **TXT** 、**DOC**和 **PDF** 格式，上传后自动重建知识库")

        with gr.Row():
            upload_btn = gr.UploadButton(
                "选择文件上传",
                file_types=[".txt", ".pdf",".doc",".docx"],
                file_count="single",
                variant="primary"
            )
            upload_status = gr.Textbox(
                label="状态",
                interactive=False,
                placeholder="就绪",
                scale=2
            )

        gr.Markdown("## 📋 已上传文档")
        doc_list = gr.Dataframe(
            value=get_document_df(),
            headers=["文件名", "大小", "上传时间"],
            datatype=["str", "str", "str"],
            interactive=False,
            label="文档列表"
        )

        with gr.Row():
            refresh_btn = gr.Button("🔄 刷新列表", variant="secondary")

        gr.Markdown("## 🗑️ 删除文档")
        with gr.Row():
            delete_dropdown = gr.Dropdown(
                label="选择要删除的文档",
                choices=get_delete_choices(),
                interactive=True,
                scale=3
            )
            delete_btn = gr.Button("删除选中", variant="stop", scale=1)

        # 事件绑定
        upload_btn.upload(
            upload_document,
            upload_btn,
            [upload_status, doc_list, delete_dropdown]
        )

        refresh_btn.click(
            refresh_list,
            None,
            doc_list
        ).then(
            update_delete_dropdown,
            None,
            delete_dropdown
        )

        delete_btn.click(
            delete_document,
            delete_dropdown,
            [doc_list, delete_dropdown, upload_status]
        )

if __name__ == "__main__":
    demo.launch(share=False, css=CUSTOM_CSS)
