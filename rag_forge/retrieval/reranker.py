"""
Rerank 重排序模块（Phase 2 实现）。

用 CrossEncoder 对检索结果重新打分排序。
模型通过 ModelScope 下载缓存，避免 HuggingFace 网络问题。
"""

import os
from sentence_transformers import CrossEncoder

# ModelScope 下载配置
MODELSCOPE_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "modelscope_cache",
)


class Reranker:
    """重排序器，从 ModelScope 本地缓存加载"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3",
                 model_path: str | None = None):
        """
        model_path: 本地 ModelScope 缓存路径
                    如果不传，自动用 MODELSCOPE_CACHE 下的路径
                    如果本地不存在，自动从 ModelScope 下载
        """
        if model_path is None:
            model_path = os.path.join(
                MODELSCOPE_CACHE, "models", model_name
            )

        if not os.path.isdir(model_path):
            # 本地没有 → 从 ModelScope 下载
            print(f"  从 ModelScope 下载 {model_name} ...")
            self._download_model(model_name, model_path)
            print(f"  下载完成")

        self.model = CrossEncoder(model_path, trust_remote_code=True)

    # ---------- 公开接口 ----------

    def rerank(self, query: str, candidates: list, top_k: int = 3):
        """
        对候选项重排序，返回 [(content, score, source)]

        参数：
            candidates: [(content, score, source), ...]
                        内部自动截断到 max_candidates 个，避免不必要的推理
        """
        # 自动截断候选数（安全兜底，hybrid_search 已经控制过一次）
        from rag_forge.config import settings
        max_candidates = getattr(settings, "RERANK_CANDIDATES", top_k + 2)
        candidates = candidates[:max_candidates]

        pairs = [(query, content) for content, _, _ in candidates]
        scores = self.model.predict(pairs, show_progress_bar=False)
        # 合并分数，按新分数降序排列
        result = []
        for i, (content, _, source) in enumerate(candidates):
            result.append((content, float(scores[i]), source))
        result.sort(key=lambda x: -x[1])
        return result[:top_k]

    # ---------- 内部方法 ----------

    @staticmethod
    def _download_model(model_name: str, local_path: str):
        """从 ModelScope 下载模型到本地"""
        from modelscope.hub.snapshot_download import snapshot_download

        cache_dir = os.path.dirname(local_path)
        os.makedirs(cache_dir, exist_ok=True)

        snapshot_download(
            model_id=model_name,
            cache_dir=cache_dir,
            local_dir=local_path,
        )
