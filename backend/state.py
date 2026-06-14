"""
运行时全局状态。

只声明变量，不在这读文件、不在这加载模型。
所有初始化在 main.py 的 startup 中完成。
"""

from typing import Optional, List, Any

vectordb: Any = None
all_chunks: List = []
reranker: Optional[Any] = None
llm: Any = None
prompts: str = ""
embeddings: Any = None          # startup 时赋值
researcher_prompt: str = ""     # startup 时赋值
writer_prompt: str = ""         # startup 时赋值
