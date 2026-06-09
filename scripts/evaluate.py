#!/usr/bin/env python
"""
RAG-Forge 评测入口

用法：
    python scripts/evaluate.py              # 对比实验（有/无 Rerank 各跑一遍）
    python scripts/evaluate.py --no-rerank  # 只跑无 Rerank
    python scripts/evaluate.py --rerank     # 只跑有 Rerank
    python scripts/evaluate.py --help       # 查看帮助
"""

import argparse
import sys
import os

# 确保项目根目录在导入路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_forge.evaluation.runner import (
    load_eval_dataset,
    init_rag,
    run_evaluation,
    print_report,
    run_comparison,
)


def main():
    parser = argparse.ArgumentParser(#在终端解析参数的工具，python自带的
        description="RAG-Forge 评测系统 — Phase 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python scripts/evaluate.py              对比实验（有/无 Rerank 各跑一遍）
  python scripts/evaluate.py --no-rerank  只跑无 Rerank
  python scripts/evaluate.py --rerank     只跑有 Rerank
        """,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--no-rerank", action="store_true", help="只用向量+关键词（不加 Rerank）")
    mode.add_argument("--rerank", action="store_true", help="使用向量+关键词+Rerank")
    mode.add_argument("--list", action="store_true", help="列出评测集内容")

    args = parser.parse_args()

    if args.list:
        dataset = load_eval_dataset()
        print(f"\n评测集共 {len(dataset)} 条：\n")
        for item in dataset:
            print(f"  [{item['id']:2d}] [{item['category']}] {item['question']}")
            print(f"         → 期望来源：{', '.join(item['reference_docs'])}")
        print()
        return

    if args.no_rerank:
        # 只跑无 Rerank
        dataset = load_eval_dataset()
        print("== 初始化 RAG 系统（无 Rerank）...")
        vectordb, all_chunks, _ = init_rag(use_reranker=False)
        report = run_evaluation(dataset, vectordb, all_chunks, reranker=None)
        print_report(report, title="无 Rerank 评测结果")
    elif args.rerank:
        # 只跑有 Rerank
        dataset = load_eval_dataset()
        print("== 初始化 RAG 系统（有 Rerank）...")
        vectordb, all_chunks, reranker = init_rag(use_reranker=True)
        report = run_evaluation(dataset, vectordb, all_chunks, reranker)
        print_report(report, title="有 Rerank 评测结果")
    else:
        # 默认：对比实验
        run_comparison()


if __name__ == "__main__":
    main()
