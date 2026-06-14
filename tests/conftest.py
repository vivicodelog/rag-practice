"""
pytest 共享配置。

作用：
    1. sys.path 设置（所有测试文件共用，不用每个文件写一遍）
    2. session 级 fixture（向量库只初始化一次，所有测试共享）
"""

import sys
import os

# 把项目根目录加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from rag_forge.config import settings
from rag_forge.embedding.embed import create_embeddings
from rag_forge.data.loader import FileSource, build_vectorstore


@pytest.fixture(scope="session")#这个函数是一个测试用的零件，pytest 会自动帮你管理它
def embeddings():#scope="session" 指定了它的生命周期
    """嵌入模型 — 只加载一次，所有测试共用"""
    return create_embeddings()


@pytest.fixture(scope="session")
def source():
    """文档数据源"""
    return FileSource(settings.DATA_DIR)


@pytest.fixture(scope="session")
def shared_vectorstore(embeddings, source):
    """建向量库 — 只跑一次"""
    print("\n正在初始化向量库（首次运行会下载模型，稍等几秒）...")
    vectordb, all_chunks, _ = build_vectorstore(
        source, embeddings, settings.CHROMA_DIR
    )
    print(f"初始化完成，共 {len(all_chunks)} 个文档块\n")
    return vectordb, all_chunks


@pytest.fixture(scope="session")
def vectordb(shared_vectorstore):
    return shared_vectorstore[0]


@pytest.fixture(scope="session")
def all_chunks(shared_vectorstore):
    return shared_vectorstore[1]
