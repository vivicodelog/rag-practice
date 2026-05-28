# 首先是导入数据库
import os
# 只导入某个函数
from dotenv import load_dotenv
import requests

# 需要加载环境变量
load_dotenv()

# 配置大模型
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyPDFLoader
# 加载文档
# # loader = TextLoader("data/test.txt", encoding="utf-8")
# loader = PyPDFLoader("data/dictionary.pdf")
all_documents = []
# 加载 TXT
try:
    loader_txt = TextLoader("data/test.txt", encoding="utf-8")
    all_documents.extend(loader_txt.load())
    print("加载 test.txt 成功")
except FileNotFoundError:
    print("test.txt 不存在或加载失败")

# 加载 PDF
try:
    loader_pdf = PyPDFLoader("data/dictionary.pdf")
    all_documents.extend(loader_pdf.load())
    print("加载 dictionary.pdf 成功")
except FileNotFoundError:
    print("dictionary.pdf 不存在或加载失败")

documents = all_documents
# 先把文档获取，进行切片
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = text_splitter.split_documents(documents)
print(f"文档已切片，共有{len(chunks)}个片段")

# 先把文档的内容切片拿过来给chroma
import chromadb
from chromadb.utils import embedding_functions
class SiliconFlowEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __call__(self, texts) :
        embeddings = []
        for text in texts:
            emb = get_embedding(text)
            if emb :
                embeddings.append(emb)
            else :
                embeddings.append([0] * 1024) 
        return embeddings

# 配置硅基流动的嵌入模型（用于向量化）
SILICON_API_KEY = "sk-slhavlgarirsrkufmiyqiebwqqhxslqbniajtkhemxaricoy"  # 替换成你刚才复制的密钥
SILICON_EMBEDDING_URL = "https://api.siliconflow.cn/v1/embeddings"
# 调用获取嵌入方法
def get_embedding(text):
    # 调用硅基流动api
    headers = {
        "Authorization": f"Bearer {SILICON_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "BAAI/bge-large-zh-v1.5",
        "input": text,
    }
    try:
        response = requests.post(SILICON_EMBEDDING_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()["data"][0]["embedding"]
        else:
            print(f"向量化失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"请求异常: {e}")

# 初始化向量库
client = chromadb.PersistentClient(path="./chroma_db")
collection_name = "my_knowledge_base_practice"



# 每次运行重新创建向量库（避免旧数据干扰）
try:
    client.delete_collection(collection_name)
    print("[INFO] 已删除旧的向量库")
except:
    pass

collection = client.create_collection(
    name=collection_name,
    embedding_function=SiliconFlowEmbeddingFunction()
)
for idx, chunk in enumerate(chunks):
    collection.add(
        documents=[chunk.page_content],
        metadatas=[chunk.metadata],
        ids=[f"doc_{idx}"]
    )
print(f"向量库已创建，共有{collection.count()}个向量")

# 把chroma处理后的数据进行匹配
def ask_question(question):
    """基于知识库回答问题"""
    results = collection.query(
        query_texts=[question],
        n_results=2
    )
    if not results["ids"]or not results['documents'][0]:
        return "文档中没有提到相关内容"
    context = "\n\n".join(results['documents'][0])

    # 对大模型的输出语句进行修饰处理
    prompt = f"""你是一个基于文档回答问题的助手。请根据以下文档内容回答用户问题。
如果文档中没有相关信息，请直接说"文档中没有提到相关内容"，不要编造。

文档内容：
{context}

用户问题：{question}

请用中文回答："""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:   
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            return answer
        else:
            return f"DeepSeek API 错误: {response.status_code}"
    except Exception as e:
        return f"请求失败: {e}"

# 先是运行方法

if __name__ == '__main__':
    while True:
        question = input("\n请输入问题（输入 q 退出）：")
        if question.lower() == 'q':
            break
        print(f'问题:{question}')
        answer = ask_question(question)
        print(f'答案:{answer}')

