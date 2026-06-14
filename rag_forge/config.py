"""
统一配置模块。

所有路径、模型名称、超参数集中在这里定义。
其他地方引用都通过 from rag_forge.config import settings 获取。
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ---------- 路径 ----------
    DATA_DIR: str = "data"
    CHROMA_DIR: str = "chroma_db"
    SYNC_STATE_FILE: str = "chroma_db/sync_state.json"
    MANIFEST_FILE: str = "data/manifest.json"

    # ---------- 嵌入模型 ----------
    EMBEDDING_MODEL_PATH: str = "./modelscope_cache/models/BAAI/bge-small-zh-v1.5"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_NORMALIZE: bool = True

    # ---------- 文本切分 ----------
    CHUNK_SIZE: int = 300
    CHUNK_OVERLAP: int = 30

    # ---------- 检索 ----------
    RETRIEVAL_TOP_K_VECTOR: int = 6
    RETRIEVAL_TOP_K_KEYWORD: int = 10
    RETRIEVAL_TOP_K_FINAL: int = 6

    # ---------- Rerank（Phase 2 启用）----------
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_MODEL_PATH: str = "./modelscope_cache/models/BAAI/bge-reranker-v2-m3"
    RERANK_TOP_K: int = 3                    # 最终保留几个结果
    RERANK_CANDIDATES: int = 8               # 送进 Reranker 的候选上限（越大越准越慢）

    # ---------- 大模型 ----------
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.1
    DEEPSEEK_API_KEY: str = ""

    # ---------- 提示词 ----------
    PROMPTS_DIR: str = "rag_forge/prompts"
    PROMPTS_DIR_AGENT: str = "rag_forge/agent/prompts"
    # ---------- 对话 ----------
    MAX_HISTORY_ROUNDS: int = 4

    def __init__(self):
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


settings = Settings()
