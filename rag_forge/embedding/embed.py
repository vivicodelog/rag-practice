"""
嵌入模型封装。

把 HuggingFaceEmbeddings 的创建集中到这里，供 Chroma 调用。
"""
from langchain_huggingface import HuggingFaceEmbeddings
from rag_forge.config import settings

def create_embeddings(
    model_path: str | None = None,
    ) -> HuggingFaceEmbeddings:
    """创建 HuggingFace 嵌入模型"""
    return HuggingFaceEmbeddings(    
        model_name=settings.EMBEDDING_MODEL_PATH if model_path is None else model_path,
        model_kwargs={"device":settings.EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": settings.EMBEDDING_NORMALIZE},
    )

