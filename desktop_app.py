# -*- coding: utf-8 -*-
"""
XCbot · 今日头条采集与自媒体AI创作工作台 - 桌面原生客户端启动器 (Desktop Native Launcher)
========================================================================================
使用 Microsoft Edge WebView2 原生无缝独立视窗，彻底告别浏览器标签栏与黑框 CMD 控制台。
"""

import os
import sys
import time
import socket
import threading
import uvicorn
import webview
from pathlib import Path

# 路径定位
BASE_DIR = Path(__file__).parent.resolve()
ICON_PATH = BASE_DIR / "static" / "app_icon.ico"

# 寻找空闲端口
def find_available_port(default_port: int = 8765) -> int:
    for port in range(default_port, default_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return default_port

def start_backend_server(port: int):
    """在子线程中静默启动 FastAPI 后台"""
    from server import app
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()

def wait_for_server(port: int, timeout: float = 5.0) -> bool:
    """等待本地后端服务就绪"""
    start_t = time.time()
    while time.time() - start_t < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.1)
    return False

def main():
    port = find_available_port(8765)

    # 1. 启动后端静默服务
    server_thread = threading.Thread(target=start_backend_server, args=(port,), daemon=True)
    server_thread.start()

    # 2. 等待服务就绪
    if not wait_for_server(port):
        print("错误: 本地后台服务启动超时！")
        sys.exit(1)

    app_url = f"http://127.0.0.1:{port}/"

    # 3. 创建原生桌面窗口 (固定视窗尺寸与缩放，提供纯正 EXE 桌面应用体感)
    window_kwargs = {
        "title": "XCbot · 今日头条文章采集与自媒体AI创作工作台",
        "url": app_url,
        "width": 1280,
        "height": 860,
        "min_size": (1180, 720),
        "text_select": True,
        "zoomable": False,
    }

    # 创建并启动窗口 (Windows 下默认使用原生 Edge Chromium / WebView2 引擎，性能极致，内存低)
    window = webview.create_window(**window_kwargs)
    
    # 启动 GUI 主循环 (阻塞直至用户关闭窗口)
    webview.start(gui="edgechromium", debug=False)
    
    # 用户关闭主窗口后退出整个进程
    sys.exit(0)

if __name__ == "__main__":
    main()
