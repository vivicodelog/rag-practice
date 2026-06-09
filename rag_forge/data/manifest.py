"""
文档清单管理。

管理 data/manifest.json，记录文件名、大小、上传时间。
函数接受 manifest_file 参数，便于测试时传入不同的路径。
"""
from datetime import datetime
import json
import os

from rag_forge.config import settings

def load_manifest(manifest_file: str):
    """读取文档清单"""
    # 从 manifest_file 路径读取 JSON，返回列表
    #       文件不存在时返回空列表
    # def load_manifest():
    if os.path.exists(manifest_file):
        with open(manifest_file, "r", encoding="utf-8") as f:#有with就相当于后面自动关闭文件
            return json.load(f)
    return []


def save_manifest(manifest: list, manifest_file: str):
    """保存文档清单到 manifest_file"""
    # 确保目录存在 → 写入 JSON（ensure_ascii=False, indent=2）
    os.makedirs(settings.DATA_DIR, exist_ok=True)#创建文件夹，如果没有就创建，否则不用，也不报错
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)#json.dump() = 把 Python 对象转换成 JSON 格式并写入文件



def sync_manifest(data_dir: str, manifest_file: str):
    """同步 manifest 与实际文件系统，返回最新的清单。

    流程：
      1. 扫描 data_dir 目录，收集真实存在的文件（扩展名白名单）
      2. 加载已有的 manifest.json
      3. 新增的文件 → 加入清单
      4. 已删除的文件 → 移出清单
      5. 已有的文件 → 更新大小和修改时间
      6. 保存并返回最新清单
    """
   # 扫描当前文件系统，收集实际存在的文件
    current_files = {}#current_files = 硬盘上真实存在的文件
    for root, _, files in os.walk(settings.DATA_DIR):
        for fname in sorted(files):
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''#取出文件的扩展名（比如 .pdf 就取出 pdf），转成小写方便比较
            if ext not in ('txt', 'pdf', 'docx', 'md', 'markdown'):
                continue
            path = os.path.join(root, fname)#拼接出完整路径
            rel_path = os.path.relpath(path, settings.DATA_DIR).replace("\\", "/")
            current_files[rel_path] = {
                "size": os.path.getsize(path),# 文档大小
                "mtime": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()# 最后修改时间
            }

    # 加载已有 manifest
    manifest = load_manifest(manifest_file)
    existing_map = {item["filename"]: item for item in manifest}#字典推导式，把列表转成字典

    new_manifest = []
    for fname, info in current_files.items():
        if fname in existing_map:
            # 已有记录 → 更新大小和修改时间（文件可能被外部修改过）
            existing_map[fname]["size"] = info["size"]
            existing_map[fname]["upload_date"] = info["mtime"]
            new_manifest.append(existing_map[fname])
        else:
            # 新文件 → 新增记录
            new_manifest.append({
                "filename": fname,
                "size": info["size"],
                "upload_date": info["mtime"]
            })

    save_manifest(new_manifest,manifest_file)
    return new_manifest
