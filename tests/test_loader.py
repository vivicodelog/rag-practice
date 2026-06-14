"""
文档加载器的单元测试。

主要测试 FileSource.get_documents() 能否正确递归加载子目录文件。

运行：
    pytest tests/test_loader.py -v
"""

from rag_forge.data.loader import FileSource


def test_get_documents_loads_subdirectory_files(tmp_path):
    """
    子目录加载测试：FileSource 应该能加载子目录中的文件。

    场景：data/
          ├── readme.txt
          └── 教程/
              └── 第一章.txt

    预期：两个文件都被加载，doc_id 包含相对路径。
    """
    # ---- 准备临时目录结构 ----
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    root_file = data_dir / "readme.txt"
    root_file.write_text("这是根目录的说明文档", encoding="utf-8")

    sub_dir = data_dir / "教程"
    sub_dir.mkdir()
    sub_file = sub_dir / "第一章.txt"
    sub_file.write_text("这是第一章的内容", encoding="utf-8")

    # ---- 执行 ----
    source = FileSource(str(data_dir))
    docs = source.get_documents()

    # ---- 验证 ----
    assert len(docs) == 2, f"应该加载 2 个文件，实际加载了 {len(docs)} 个"

    doc_ids = [doc_id for doc_id, _, _ in docs]
    rel_paths = [did.split("::")[0] for did in doc_ids]

    assert "readme.txt" in rel_paths, "根目录的 readme.txt 应该被加载"
    assert "教程/第一章.txt" in rel_paths, \
        f"子目录的 '教程/第一章.txt' 应该被加载。实际路径：{rel_paths}"

    assert "第一章.txt" not in rel_paths, \
        "doc_id 应该用相对路径，不能只有文件名（否则子目录文件无法区分）"


def test_get_documents_skips_unsupported_extensions(tmp_path):
    """
    扩展名过滤测试：不支持的扩展名应该被跳过。

    场景：data/
          ├── readme.txt          ← 支持
          ├── image.png           ← 不支持
          └── 笔记.md             ← 支持

    预期：只加载 txt 和 md，跳过 png。
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / "readme.txt").write_text("说明", encoding="utf-8")
    (data_dir / "image.png").write_text("假装是图片", encoding="utf-8")
    (data_dir / "笔记.md").write_text("# 标题\n内容", encoding="utf-8")

    source = FileSource(str(data_dir))
    docs = source.get_documents()

    assert len(docs) == 2, f"应该加载 2 个支持的文件，实际加载 {len(docs)} 个"

    doc_ids = [did for did, _, _ in docs]
    all_content = " ".join(text for _, text, _ in docs)

    assert any("readme.txt" in did for did in doc_ids), "readme.txt 应该被加载"
    assert any("笔记.md" in did for did in doc_ids), "笔记.md 应该被加载"
    assert "png" not in all_content, "image.png 不应该被加载"


def test_get_documents_empty_directory(tmp_path):
    """
    空目录健壮性测试：目录为空时返回空列表，不报错。

    场景：data/ （空目录）
    预期：返回 []，不抛异常
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    source = FileSource(str(data_dir))
    docs = source.get_documents()

    assert docs == [], "空目录应该返回空列表"


def test_get_documents_handles_mixed_subdirectory_structure(tmp_path):
    """
    复杂目录结构测试：多级子目录和多种文件类型混合。

    场景：data/
          ├── 基础/          ← 第一层
          │   ├── 入门.txt
          │   └── 进阶/      ← 第二层
          │       └── 高级技巧.txt
          └── 参考/
              └── 手册.md

    预期：3 个支持的文件全部被加载。
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    basic = data_dir / "基础"
    basic.mkdir()
    (basic / "入门.txt").write_text("入门内容", encoding="utf-8")

    advanced = basic / "进阶"
    advanced.mkdir()
    (advanced / "高级技巧.txt").write_text("高级内容", encoding="utf-8")

    ref = data_dir / "参考"
    ref.mkdir()
    (ref / "手册.md").write_text("# 手册", encoding="utf-8")

    source = FileSource(str(data_dir))
    docs = source.get_documents()

    assert len(docs) == 3, f"应该加载 3 个文件，实际加载 {len(docs)} 个"

    rel_paths = [did.split("::")[0] for did, _, _ in docs]
    expected = ["基础/入门.txt", "基础/进阶/高级技巧.txt", "参考/手册.md"]
    for path in expected:
        assert path in rel_paths, f"缺少：{path}"


def test_get_documents_doc_id_uses_relative_path(tmp_path):
    """
    doc_id 格式测试：确保 doc_id 使用相对路径，保证唯一性。

    不同子目录下可能有同名文件（比如两个 readme.txt），
    doc_id 必须能区分它们。
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / "A").mkdir()
    (data_dir / "B").mkdir()
    (data_dir / "A" / "readme.txt").write_text("A 的说明", encoding="utf-8")
    (data_dir / "B" / "readme.txt").write_text("B 的说明", encoding="utf-8")

    source = FileSource(str(data_dir))
    docs = source.get_documents()

    assert len(docs) == 2, "两个同名文件都应该被加载"

    rel_paths = [did.split("::")[0] for did, _, _ in docs]
    assert "A/readme.txt" in rel_paths
    assert "B/readme.txt" in rel_paths
    assert rel_paths.count("readme.txt") == 0, "不能只用文件名，要用相对路径"
