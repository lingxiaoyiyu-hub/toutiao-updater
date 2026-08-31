# -*- coding: utf-8 -*-
"""
纯净源码备份打包器 (Clean Source Code Backup Tool)
=================================================
将可二次开发的全部核心源码、静态资源、开发文档与辅助脚本打包为精简 ZIP 备份。
自动排除 dist/、release/、__pycache__、爬虫临时输出等数以百兆的大体积构建产物。
"""

import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.resolve()
TIMESTAMP = datetime.now().strftime("%Y%m%d")
OUTPUT_ZIP = BASE_DIR / f"今日头条采集与AI创作工作台_纯净二次开发源码包_v2.5.0_{TIMESTAMP}.zip"

EXCLUDE_DIRS = {
    "dist",
    "release",
    "build",
    "__pycache__",
    "toutiao_output",
    "test_img_output",
    ".git",
    ".vscode",
    ".idea",
    "env",
    "venv",
    ".venv"
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".spec",
    ".log"
}

EXCLUDE_FILES = {
    "license.dat",
    ".sys_state.dat"
}

def should_exclude(path: Path) -> bool:
    rel_parts = path.relative_to(BASE_DIR).parts
    for part in rel_parts:
        if part in EXCLUDE_DIRS:
            return True
        if part.startswith("."):
            if part not in [".gitignore"]:
                return True
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.name.endswith(".zip") and "纯净二次开发源码包" in path.name:
        return True
    return False

def make_backup():
    print("=" * 60)
    print("   今日头条采集与AI创作工作台 - 纯净二次开发源码备份")
    print("=" * 60)
    print(f"[*] 扫描目录: {BASE_DIR}")
    print(f"[*] 输出压缩包: {OUTPUT_ZIP.name}")

    count = 0
    total_bytes = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(BASE_DIR):
            root_path = Path(root)
            
            # 过滤排除目录
            dirs[:] = [d for d in dirs if not should_exclude(root_path / d)]

            for file in files:
                file_path = root_path / file
                if should_exclude(file_path):
                    continue

                rel_path = file_path.relative_to(BASE_DIR)
                zipf.write(file_path, arcname=str(rel_path))
                count += 1
                total_bytes += file_path.stat().st_size
                print(f"  + [打包] {rel_path}")

    zip_size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    raw_size_mb = total_bytes / (1024 * 1024)

    print("=" * 60)
    print(f"[OK] 纯净源码包备份生成成功！")
    print(f"     文件数量: {count} 个文件")
    print(f"     原始大小: {raw_size_mb:.2f} MB")
    print(f"     压缩包大小: {zip_size_mb:.2f} MB (极度轻量)")
    print(f"     保存路径: {OUTPUT_ZIP}")
    print("=" * 60)

if __name__ == "__main__":
    make_backup()
