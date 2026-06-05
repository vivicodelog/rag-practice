"""
日志工具。目前用 print 封装，Phase 4 升级到 loguru。
"""
from datetime import datetime


def log_info(tag: str, message: str, **extra):
    parts = [f"[{tag}]", message] + [f"{k}={v}" for k, v in extra.items()]
    print(f"[{datetime.now().isoformat()}] {' | '.join(parts)}")


def log_error(tag: str, message: str, **extra):
    parts = [f"[{tag}] ❌", message] + [f"{k}={v}" for k, v in extra.items()]
    print(f"[{datetime.now().isoformat()}] {' | '.join(parts)}")
