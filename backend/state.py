"""
运行时全局状态。

vectordb、all_chunks、reranker 在 main.py 启动时初始化后存到这里，
router.py 里的接口从这取。
"""

from typing import Optional, List, Any

from torch import embedding

from rag_forge.embedding.embed import create_embeddings


vectordb: Any = None
all_chunks: List = []
reranker: Optional[Any] = None
llm: Any = None
prompts: str = ""
embeddings: Any = create_embeddings()
