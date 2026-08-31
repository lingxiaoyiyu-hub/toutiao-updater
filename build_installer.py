# -*- coding: utf-8 -*-
"""
XCbot · 今日头条采集与自媒体创作工作台 - 一键桌面端打包构建脚本
================================================================
使用 PyInstaller + WebView2 构建独立无黑框原生可执行文件 (.exe)。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ICON_PATH = BASE_DIR / "static" / "app_icon.ico"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

def build():
    print("=" * 60)
    print("   XCbot · 今日头条采集与自媒体创作工作台 - 桌面端构建打包")
    print("=" * 60)

    # 1. 检查 PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] 正在安装 PyInstaller 打包套件...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. 清理历史构建
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR, ignore_errors=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    # 3. 构造 PyInstaller 参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",                       # 目录模式 (启动极速、防临时目录卡顿)
        "--windowed",                     # 纯原生窗口，彻底隐藏黑框 CMD 控制台
        "--name=ToutiaoStudio",           # 程序名
        f"--icon={ICON_PATH}",            # 专属应用高保真图标
        f"--add-data={BASE_DIR / 'static'};static",
        f"--add-data={BASE_DIR / 'modules'};modules",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespans",
        "--hidden-import=uvicorn.lifespans.auto",
        "--hidden-import=starlette.routing",
        "--hidden-import=fastapi",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
        "--hidden-import=webview",
        "--hidden-import=cryptography",
        "--hidden-import=patchright",
        "--hidden-import=modules.app_config",
        "--hidden-import=modules.media_writer",
        "--hidden-import=modules.viral_analyzer",
        "--hidden-import=modules.docx_exporter",
        "--hidden-import=modules.security_guard",
        "--hidden-import=modules.toutiao_adapter",
        str(BASE_DIR / "desktop_app.py")
    ]

    print("\n[*] 正在编译生成独立桌面客户端程序...")
    try:
        subprocess.check_call(cmd, cwd=str(BASE_DIR))

        # 4. 拷贝 patchright 浏览器驱动至发行目录 (确保绝对离线单机可用)
        appdata_browsers = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        target_browsers = DIST_DIR / "ToutiaoStudio" / "_internal" / "patchright" / "driver" / "package" / ".local-browsers"
        if appdata_browsers.exists():
            print("\n[*] 正在同步浏览器自动化内核至程序包...")
            os.makedirs(target_browsers, exist_ok=True)
            for item in ["chromium_headless_shell-1228"]:
                src_b = appdata_browsers / item
                if src_b.exists():
                    dst_b = target_browsers / item
                    if not dst_b.exists():
                        shutil.copytree(src_b, dst_b)
            print("[OK] 浏览器自动化内核已内嵌至客户端发行目录。")

        print("\n" + "=" * 60)
        print(" [OK] 桌面客户端构建完成！")
        print("=" * 60)
        output_exe = DIST_DIR / "ToutiaoStudio" / "ToutiaoStudio.exe"
        print(f" 输出程序路径: {output_exe}")
        print(" 您可以将 dist/ToutiaoStudio/ 文件夹整体打包为 Zip 或制作安装包分发给客户。")
    except Exception as e:
        print(f"\n[X] 构建失败: {e}")

if __name__ == "__main__":
    build()
