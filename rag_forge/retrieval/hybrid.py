"""
混合检索：向量搜索 + 关键词搜索 → 统一合并排序。

Phase 2 时会集成 Reranker 精排。
"""

import os

from rag_forge.retrieval.keyword import keyword_search
from rag_forge.retrieval.vector import vector_search


def hybrid_search(query: str, vectordb, all_chunks: list,
                  top_k: int = 6, reranker=None):
    """
    混合检索 + 可选 Rerank。

    返回 [(content, score, source)]

    优化：送入 Reranker 前只保留 top_k * 2 个候选项，
          减少 CrossEncoder 推理量（重排序只需排前几名）。
    """
    vector_results = vector_search(query, vectordb, top_k)
    kw_results = keyword_search(query, all_chunks, top_k)
    merged = {}  # content -> {"score": float, "source": str}

    # 加关键词结果
    for score, content, source in kw_results:
        merged[content] = {"score": score, "source": source}

    # 加向量结果（如果已存在，取最高分）
    for score, content, source in vector_results:
        if content in merged:
            merged[content]["score"] = max(merged[content]["score"], score)
        else:
            merged[content] = {"score": score, "source": source}

    # 按综合分数降序排列
    sorted_items = sorted(merged.items(), key=lambda x: -x[1]["score"])

    # 如果有 Reranker → 精排（只送前 top_k + 2 个候选，减少推理量）
    if reranker is not None:
        from rag_forge.config import settings
        max_candidates = getattr(settings, "RERANK_CANDIDATES", top_k + 2)
        candidates = [(c, info["score"], info["source"])
                      for c, info in sorted_items[:max_candidates]]
        return reranker.rerank(query, candidates)

    # 否则按合并分数直接取 top_k
    return [(c, info["score"], info["source"]) for c, info in sorted_items[:top_k]]

