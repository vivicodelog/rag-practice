#!/usr/bin/env python
"""
Workflow 回答质量评测 — 入口

用法：
    python scripts/eval_workflow.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_forge.evaluation.workflow_eval import main

if __name__ == "__main__":
    main()
