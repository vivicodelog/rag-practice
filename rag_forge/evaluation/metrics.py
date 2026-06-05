"""
评测指标模块

提供 RAG 系统的核心评测指标计算：
- Hit Rate（命中率）：正确答案来源是否出现在检索结果中
- MRR（Mean Reciprocal Rank）：第一个正确答案的排名的倒数
- Precision@k（精确率）：前 k 个结果中有多少是正确答案
"""

import os
from typing import List, Dict, Tuple


def extract_source_filename(source_path: str) -> str:
    """从完整路径中提取文件名，用于匹配 reference_docs"""
    return os.path.basename(source_path)


def is_relevant(result_source: str, reference_docs: List[str]) -> bool:
    """判断一个检索结果的来源是否在参考文档列表中"""
    fname = extract_source_filename(result_source)
    return fname in reference_docs


def hit_at_k(results: List[Tuple], reference_docs: List[str], k: int = None) -> bool:
    """
    Hit@k：前 k 个结果中是否包含参考文档？

    参数：
        results: [(content, score, source), ...]
        reference_docs: 期望的文档名列表，如 ["test.txt"]
        k: 只看前几个结果（默认全部）

    返回：
        True 表示至少有一个参考文档被命中
    """
    if k is not None:
        results = results[:k]
    return any(is_relevant(source, reference_docs) for _, _, source in results)


def reciprocal_rank(results: List[Tuple], reference_docs: List[str]) -> float:
    """
    RR（Reciprocal Rank）：第一个参考文档的排名倒数

    如果第一个参考文档在第 3 位，RR = 1/3
    如果没有命中，RR = 0
    """
    for rank, (_, _, source) in enumerate(results, start=1):
        if is_relevant(source, reference_docs):
            return 1.0 / rank
    return 0.0


def precision_at_k(results: List[Tuple], reference_docs: List[str], k: int) -> float:
    """
    Precision@k（P@k）：前 k 个结果中参考文档的比例

    例：top-3 中有 2 个来自参考文档 → P@3 = 2/3 ≈ 0.667
    """
    top_k = results[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for _, _, source in top_k if is_relevant(source, reference_docs))
    return hits / len(top_k)


def recall_at_k(results: List[Tuple], reference_docs: List[str], k: int) -> float:
    """
    Recall@k：前 k 个结果覆盖了多少参考文档

    注意：如果只有 1 个参考文档，Recall@k 和 Hit@k 含义相同。
    如果有多个参考文档，Recall 衡量覆盖了多少个。
    """
    top_k = results[:k]
    if not reference_docs:
        return 0.0
    retrieved_docs = set()
    for _, _, source in top_k:
        fname = extract_source_filename(source)
        if fname in reference_docs:
            retrieved_docs.add(fname)
    return len(retrieved_docs) / len(reference_docs)


def compute_all_metrics(
    results: List[Tuple],
    reference_docs: List[str],
    ks: List[int] = None,
) -> Dict[str, float]:
    """
    一次性计算所有常用指标

    参数：
        results: [(content, score, source), ...]
        reference_docs: 期望的文档名列表
        ks: 要计算的 k 值列表，默认 [1, 3, 5]

    返回：
        {
            "hit@1": 0.5,
            "hit@3": 1.0,
            "hit@5": 1.0,
            "mrr": 0.75,
            "p@3": 0.667,
            "p@5": 0.4,
            "recall@3": 1.0,
        }
    """
    if ks is None:
        ks = [1, 3, 5]

    metrics = {}

    for k in ks:
        metrics[f"hit@{k}"] = 1.0 if hit_at_k(results, reference_docs, k) else 0.0

    for k in ks:
        metrics[f"p@{k}"] = precision_at_k(results, reference_docs, k)

    for k in ks:
        metrics[f"recall@{k}"] = recall_at_k(results, reference_docs, k)

    metrics["mrr"] = reciprocal_rank(results, reference_docs)

    return metrics


def average_metrics(all_metrics: List[Dict[str, float]]) -> Dict[str, float]:
    """对多条 query 的指标取平均"""
    if not all_metrics:
        return {}
    avg = {}
    for key in all_metrics[0]:
        values = [m[key] for m in all_metrics]
        avg[key] = sum(values) / len(values)
    return avg
