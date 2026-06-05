"""
嵌入模型封装。

把 HuggingFaceEmbeddings 的创建集中到这里，供 Chroma 调用。
"""
from langchain_huggingface import HuggingFaceEmbeddings


def create_embeddings(
    model_path: str = None,
    device: str = "cpu",
    normalize: bool = True,
) -> HuggingFaceEmbeddings:
    """创建 HuggingFace 嵌入模型"""
    return HuggingFaceEmbeddings(    
        model_name="./modelscope_cache/models/BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

