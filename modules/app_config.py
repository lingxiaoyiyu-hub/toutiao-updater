# -*- coding: utf-8 -*-
"""
全局持久化配置与路径管理器 (Global Persistent Config & Storage Manager)
========================================================================
彻底解决 PyInstaller 单文件模式 (_MEIPASS 临时目录解压)、Program Files 安装目录只读、
以及跨进程重启时丢失会员激活状态 (license.dat) 和 AI 模型配置 (ai_config.json) 的问题。
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, List


def get_app_data_dir() -> Path:
    """
    获取全局统一的用户数据持久化存储目录（100% 用户可读写且重启绝对不丢失）
    - Windows: %APPDATA%\\XCbot_ToutiaoStudio (即 C:\\Users\\<用户名>\\AppData\\Roaming\\XCbot_ToutiaoStudio)
    - Linux/Mac: ~/.xcbot_toutiaostudio
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            p = Path(app_data) / "XCbot_ToutiaoStudio"
            p.mkdir(parents=True, exist_ok=True)
            return p

    home = Path.home()
    p = home / ".xcbot_toutiaostudio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_output_dir() -> Path:
    """
    获取爬虫与 Word 导出的根目录
    优先选择 exe/脚本同级目录 toutiao_output，如果只读（如 Program Files），回退到 APPDATA / Documents
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent.parent

    target_out = exe_dir / "toutiao_output"
    try:
        target_out.mkdir(parents=True, exist_ok=True)
        # 测试是否具有写权限
        test_f = target_out / ".perm_check"
        test_f.write_text("ok", encoding="utf-8")
        test_f.unlink(missing_ok=True)
        return target_out
    except Exception:
        fallback = get_app_data_dir() / "toutiao_output"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
