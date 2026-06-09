"""
评测运行器

负责：
1. 加载评测数据集
2. 初始化 RAG 系统（配置是否使用 Rerank）
3. 逐条跑问题，收集检索结果
4. 计算指标，生成报告
"""

import json
import os
import time
from typing import List, Dict, Optional

from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore, need_rebuild
from rag_forge.retrieval.hybrid import hybrid_search
from rag_forge.retrieval.reranker import Reranker
from rag_forge.evaluation.metrics import compute_all_metrics, average_metrics


def load_eval_dataset(path: str = None) -> List[Dict]:
    """加载评测数据集"""
    if path is None:
        # 默认路径：项目根目录下的 tests/eval_dataset.json
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..",
            "tests",
            "eval_dataset.json",
        )
    with open(path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    print(f"  加载评测集：{len(dataset)} 条\n")
    return dataset


def init_rag(use_reranker: bool = True):
    """
    初始化 RAG 系统

    参数：
        use_reranker: 是否加载 Reranker

    返回：
        (vectordb, all_chunks, reranker)
    """
    embeddings = create_embeddings()
    source = FileSource(settings.DATA_DIR)
    sync_state = getattr(settings, "SYNC_STATE_FILE", "./chroma_db/sync_state.json")

    should_rebuild, existing_vdb, _ = need_rebuild(source, sync_state)
    if should_rebuild or existing_vdb is None:
        vectordb, all_chunks, _ = build_vectorstore(source, embeddings, settings.CHROMA_DIR)
    else:
        vectordb = existing_vdb
        # Load chunks from chunks.json
        chunks_path = os.path.join(settings.CHROMA_DIR, "chunks.json")
        if os.path.exists(chunks_path):
            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)
            print(f"  从 chunks.json 加载了 {len(all_chunks)} 个片段")
        else:
            all_chunks = []

    reranker = None
    if use_reranker:
        try:
            reranker = Reranker()
            print("  Reranker 加载成功")
        except Exception as e:
            print(f"  [!] Reranker 加载失败，将不使用重排序：{e}")

    return vectordb, all_chunks, reranker


def evaluate_single(
    question: str,
    reference_docs: List[str],
    vectordb,
    all_chunks: List,
    reranker,
    top_k: int = 6,
) -> Dict:
    """跑一条评测数据，返回指标和详情"""
    results = hybrid_search(
        query=question,
        vectordb=vectordb,
        all_chunks=all_chunks,
        top_k=top_k,
        reranker=reranker,
    )

    metrics = compute_all_metrics(results, reference_docs, ks=[1, 3, 5])#---hit@1\3\5

    # 记录命中的文档名
    retrieved_sources = []
    for content, score, source in results:
        retrieved_sources.append(os.path.basename(source) if source else "未知来源")

    return {
        "metrics": metrics,
        "retrieved_sources": retrieved_sources,
        "top_result": results[0][0][:80] + "..." if results else "",
    }


def run_evaluation(
    dataset: List[Dict],
    vectordb,
    all_chunks: List,
    reranker,
    top_k: int = 6,
    verbose: bool = True,
) -> Dict:
    """跑完整评测，逐条调用，返回汇总报告"""
    all_metrics = []
    details = []

    for item in dataset:
        qid = item["id"]
        question = item["question"]
        ref_docs = item["reference_docs"]
        category = item.get("category", "未分类")

        if verbose:
            print(f"  [{qid:2d}] {question}")

        result = evaluate_single(question, ref_docs, vectordb, all_chunks, reranker, top_k)
        metrics = result["metrics"]
        all_metrics.append(metrics)

        details.append({
            "id": qid,
            "question": question,
            "reference_docs": ref_docs,
            "category": category,
            "metrics": metrics,
            "hit": metrics.get("hit@3", 0) > 0,  # 以 hit@3 作为"是否命中"的判断
            "retrieved_sources": result["retrieved_sources"],
        })

        if verbose:
            hit = "[OK]" if metrics.get("hit@3", 0) > 0 else "[MISS]"
            print(f"      hit@3={hit}  MRR={metrics['mrr']:.3f}  "
                  f"源={result['retrieved_sources'][:3]}")

    averages = average_metrics(all_metrics)

    return {
        "averages": averages,
        "details": details,
        "total": len(dataset),
        "hit_count": sum(1 for d in details if d["hit"]),
        "top_k": top_k,
    }


def print_report(report: Dict, title: str = "评测报告"):
    """打印评测报告"""
    avg = report["averages"]

    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print(f"  总问题数：{report['total']}")
    print(f"  命中数（Hit@3）：{report['hit_count']}/{report['total']}")
    print(f"  Hit Rate (hit@3)：{report['hit_count'] / report['total']:.1%}")
    print()
    print(f"  [指标]")
    print(f"     Hit@1：  {avg.get('hit@1', 0):.1%}")
    print(f"     Hit@3：  {avg.get('hit@3', 0):.1%}")
    print(f"     Hit@5：  {avg.get('hit@5', 0):.1%}")
    print(f"     MRR：    {avg.get('mrr', 0):.3f}")
    print(f"     P@3：    {avg.get('p@3', 0):.1%}")
    print(f"     P@5：    {avg.get('p@5', 0):.1%}")
    print()
#Hit@1  → 只看第 1 条结果有没有命中
#Hit@3  → 看前 3 条结果里有没有命中的
#Hit@5  → 看前 5 条结果里有没有命中的

    # 按分类统计
    categories = {}
    for d in report["details"]:
        cat = d["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "hits": 0, "mrr_sum": 0.0}
        categories[cat]["total"] += 1
        if d["hit"]:
            categories[cat]["hits"] += 1
        categories[cat]["mrr_sum"] += d["metrics"]["mrr"]

    print(f"  [分类统计]")
    for cat, stats in sorted(categories.items()):
        hit_rate = stats["hits"] / stats["total"] if stats["total"] > 0 else 0
        avg_mrr = stats["mrr_sum"] / stats["total"] if stats["total"] > 0 else 0
        print(f"     {cat}：{stats['hits']}/{stats['total']}  "
              f"HR={hit_rate:.0%}  MRR={avg_mrr:.3f}")

    # 未命中的问题
    misses = [d for d in report["details"] if not d["hit"]]
    if misses:
        print()
        print(f"  [!] 未命中（{len(misses)} 条）：")
        for d in misses:
            print(f"     [{d['id']}] {d['question']}")
            print(f"           期望来源：{d['reference_docs']}")
            print(f"           实际来源：{d['retrieved_sources'][:3]}")

    print("=" * 60)


def run_comparison():
    """
    跑对比实验：有 Rerank vs 无 Rerank

    优化：只初始化一次 vectordb + all_chunks，两次评测复用，
          避免第二次重复加载 embedding 模型。
    """
    print("=" * 60)
    print("  [RAG-Forge 评测系统]")
    print("  Phase 3：对比实验 -- Rerank 效果评估")
    print("=" * 60)
    print()

    dataset = load_eval_dataset()

    # 只初始化一次核心 RAG 状态（embedding + vectorstore）
    print("== 初始化 RAG 系统...")
    vectordb, all_chunks, _ = init_rag(use_reranker=False)

    # ---- 第一轮：无 Rerank ----
    print("\n-- 跑评测：无 Rerank")
    t0 = time.time()
    report_no_rerank = run_evaluation(dataset, vectordb, all_chunks, reranker=None, verbose=True)
    t1 = time.time()
    print_report(report_no_rerank, title="无 Rerank 结果")
    print(f"  耗时：{t1 - t0:.1f}s\n")

    # ---- 第二轮：有 Rerank（复用 vectordb/all_chunks）----
    print("== 加载 Reranker...")
    reranker = None
    try:
        reranker = Reranker()
        print("  Reranker 加载成功")
    except Exception as e:
        print(f"  [!] Reranker 加载失败：{e}")

    print("\n-- 跑评测：有 Rerank")
    t2 = time.time()
    report_with_rerank = run_evaluation(dataset, vectordb, all_chunks, reranker, verbose=True)
    t3 = time.time()
    print_report(report_with_rerank, title="有 Rerank 结果")
    print(f"  耗时：{t3 - t2:.1f}s\n")

    # 对比总结
    print("\n" + "=" * 60)
    print("  [对比总结]")
    print("=" * 60)

    baseline = report_no_rerank["averages"]
    improved = report_with_rerank["averages"]
    keys = ["hit@1", "hit@3", "hit@5", "mrr", "p@3"]
    for key in keys:
        b = baseline.get(key, 0)
        i = improved.get(key, 0)
        diff = i - b
        arrow = "[+]" if diff > 0 else ("[-]" if diff < 0 else "[=]")
        print(f"  {key:8s}  无Rerank={b:.1%}  有Rerank={i:.1%}  {arrow} {diff:+.1%}")
    print()

    hr_no = report_no_rerank["hit_count"]
    hr_with = report_with_rerank["hit_count"]
    total = report_no_rerank["total"]
    print(f"  Hit@3：  {hr_no}/{total} ({hr_no/total:.1%}) -> "
          f"{hr_with}/{total} ({hr_with/total:.1%})  "
          f"{'[+]' if hr_with > hr_no else '[-]'}{abs(hr_with - hr_no)}")
    print("=" * 60)
