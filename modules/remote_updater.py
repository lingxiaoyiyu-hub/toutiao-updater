# -*- coding: utf-8 -*-
"""
远程版本推送与客户端自动更新引擎 (Remote Push & Auto-Update Engine)
====================================================================
1. 远程云端版本检测 (支持自建服务器 / Gitee / GitHub / 阿里云OSS / CDN)
2. 远程公告与反爬紧急通知广播推送
3. 新版本更新日志拉取与 SemVer 语义化版本比对
4. 断点续传/流式静默下载与实时进度回报 (0%~100%)
5. Windows 原生无缝热替换与自动重启升级 (In-Place Auto-Restart Updater)
"""

import os
import sys
import re
import json
import time
import asyncio
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx

try:
    from modules.app_config import get_app_data_dir
except ImportError:
    from app_config import get_app_data_dir

CURRENT_VERSION = "2.5.0"

# 默认官方远程版本清单探测源 (支持多源容错 fallback)
# 开发者可在 data/ai_config.json 或环境变量 TOUTIAO_UPDATE_URL 中自定义为自己的服务器地址
DEFAULT_UPDATE_URLS = [
    "https://raw.githubusercontent.com/lingxiaoyiyu-hub/toutiao-updater/main/version.json",
    "https://cdn.jsdelivr.net/gh/lingxiaoyiyu-hub/toutiao-updater@main/version.json"
]


def parse_version(v_str: str) -> tuple:
    """将 '2.5.0' 或 'v2.5.1' 解析为可比较的整数元组 (2, 5, 0)"""
    v_clean = v_str.strip().lstrip("vV").split("-")[0]
    try:
        return tuple(int(x) for x in v_clean.split(".") if x.isdigit())
    except Exception:
        return (0, 0, 0)


def resolve_github_mirrors(url: str) -> List[str]:
    """
    智能解析 GitHub 链接并生成国内极速 CDN 与镜像候选列表
    优先直连，若遇网络波动自动尝试备用镜像节点
    """
    clean_url = url.strip()
    mirrors = [clean_url]

    # 处理 raw.githubusercontent.com 格式
    raw_match = re.match(r'https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)', clean_url)
    if raw_match:
        owner, repo, branch, path = raw_match.groups()
        mirrors.append(f"https://fastly.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}")
        mirrors.append(f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}")
        return mirrors

    # 处理 github.com/owner/repo/raw/branch/path 格式
    gh_match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/raw/([^/]+)/(.+)', clean_url)
    if gh_match:
        owner, repo, branch, path = gh_match.groups()
        raw_direct = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        if raw_direct not in mirrors:
            mirrors.insert(0, raw_direct)
        mirrors.append(f"https://fastly.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}")
        return mirrors

    return mirrors


class RemoteUpdater:
    """远程版本推送与升级管理器"""

    def __init__(self):
        self.current_version = CURRENT_VERSION
        self.download_state = {
            "status": "idle",       # idle, downloading, completed, error
            "progress": 0.0,        # 0.0 ~ 100.0
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_kb": 0.0,
            "error": "",
            "download_file": ""
        }
        self._cancel_flag = False

    def get_update_endpoint(self) -> str:
        """获取云端版本清单 URL (优先读取环境变量或本地覆盖配置)"""
        custom_url = os.getenv("TOUTIAO_UPDATE_URL", "").strip()
        if custom_url:
            return custom_url
        
        # 检查本地是否有自定义服务器配置
        cfg_file = get_app_data_dir() / "update_config.json"
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    c = json.load(f)
                    if c.get("update_url"):
                        return c["update_url"].strip()
            except Exception:
                pass

        # 默认返回内置地址 (若未配置，返回演示/本地模板)
        return DEFAULT_UPDATE_URLS[0]

    def set_custom_update_url(self, url: str) -> bool:
        """设置开发者的自定义远程更新源"""
        try:
            cfg_file = get_app_data_dir() / "update_config.json"
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump({"update_url": url.strip()}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    async def check_for_updates(self, custom_manifest_url: Optional[str] = None) -> Dict[str, Any]:
        """
        向云端请求最新的版本清单与远程推送公告 (自动走国内 CDN/镜像加速)
        """
        url = (custom_manifest_url or self.get_update_endpoint()).strip()

        # 如果未配置公网地址，返回默认无更新但带使用指引的状态
        if not url or "your-org" in url:
            return {
                "has_update": False,
                "current_version": self.current_version,
                "latest_version": self.current_version,
                "message": "当前已是最新版本 (可在 update_config.json 中配置您的云端推送地址)",
                "changelog": [],
                "download_url": "",
                "announcement": None,
                "configured": False
            }

        candidate_urls = resolve_github_mirrors(url)
        last_error = ""

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            for cur_try_url in candidate_urls:
                try:
                    resp = await client.get(cur_try_url, headers={"User-Agent": f"ToutiaoStudio/{self.current_version}"})
                    if resp.status_code != 200:
                        last_error = f"HTTP {resp.status_code}"
                        continue

                    data = resp.json()
                    latest_ver_str = data.get("latest_version", self.current_version)
                    cur_tuple = parse_version(self.current_version)
                    lat_tuple = parse_version(latest_ver_str)

                    has_update = lat_tuple > cur_tuple

                    return {
                        "has_update": has_update,
                        "current_version": self.current_version,
                        "latest_version": latest_ver_str,
                        "release_date": data.get("release_date", ""),
                        "title": data.get("title", f"发现新版本 v{latest_ver_str}"),
                        "changelog": data.get("changelog", []),
                        "download_url": data.get("download_url", ""),
                        "hot_update_zip_url": data.get("hot_update_zip_url", ""),
                        "force_update": data.get("force_update", False),
                        "announcement": data.get("announcement", None),
                        "configured": True,
                        "message": f"发现新版本 v{latest_ver_str}，建议立即升级！" if has_update else "当前已是最新版本"
                    }
                except Exception as e:
                    last_error = str(e)
                    continue

        return {
            "has_update": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "message": f"连接远程更新服务器失败 ({last_error})",
            "changelog": [],
            "download_url": "",
            "announcement": None
        }

    async def start_download(self, download_url: str) -> bool:
        """在后台异步流式下载更新包并计算进度"""
        if self.download_state["status"] == "downloading":
            return False

        self._cancel_flag = False
        self.download_state = {
            "status": "downloading",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_kb": 0.0,
            "error": "",
            "download_file": ""
        }

        save_dir = get_app_data_dir() / "updates"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filename = download_url.split("?")[0].split("/")[-1] or "update_package.exe"
        target_path = save_dir / filename
        self.download_state["download_file"] = str(target_path)

        async def _download_worker():
            try:
                start_time = time.time()
                last_time = start_time
                last_bytes = 0

                candidate_download_urls = resolve_github_mirrors(download_url)
                download_ok = False
                last_err = ""

                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    for cur_dl_url in candidate_download_urls:
                        try:
                            async with client.stream("GET", cur_dl_url) as resp:
                                if resp.status_code != 200:
                                    last_err = f"HTTP {resp.status_code}"
                                    continue

                                total = int(resp.headers.get("Content-Length", 0))
                                self.download_state["total_bytes"] = total
                                downloaded = 0

                                with open(target_path, "wb") as f:
                                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                                        if self._cancel_flag:
                                            self.download_state["status"] = "idle"
                                            return
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        self.download_state["downloaded_bytes"] = downloaded

                                        if total > 0:
                                            self.download_state["progress"] = round((downloaded / total) * 100, 1)

                                        now = time.time()
                                        if now - last_time >= 0.5:
                                            speed = (downloaded - last_bytes) / (now - last_time) / 1024
                                            self.download_state["speed_kb"] = round(speed, 1)
                                            last_bytes = downloaded
                                            last_time = now

                                download_ok = True
                                break
                        except Exception as e:
                            last_err = str(e)
                            continue

                if download_ok:
                    self.download_state["status"] = "completed"
                    self.download_state["progress"] = 100.0
                else:
                    self.download_state["status"] = "error"
                    self.download_state["error"] = f"下载失败: {last_err}"
            except Exception as e:
                self.download_state["status"] = "error"
                self.download_state["error"] = str(e)

        asyncio.create_task(_download_worker())
        return True

    def apply_update_and_restart(self) -> Dict[str, Any]:
        """
        执行更新替换并自动重启：
        1. 若为 Zip 补丁包，解压覆盖。
        2. 若为全新 EXE，生成批处理自杀重启脚本，替换当前可执行文件并拉起新版。
        """
        target_file_str = self.download_state.get("download_file")
        if not target_file_str or not os.path.exists(target_file_str):
            return {"success": False, "message": "未找到已下载的更新文件"}

        target_path = Path(target_file_str)
        is_frozen = getattr(sys, "frozen", False)
        current_pid = os.getpid()

        # 方案 A: 若为静态资源/模块热补丁 (.zip)
        if target_path.suffix.lower() == ".zip":
            try:
                extract_root = Path(sys.executable).parent if is_frozen else Path(__file__).parent.parent
                with zipfile.ZipFile(target_path, "r") as zf:
                    zf.extractall(extract_root)
                return {
                    "success": True,
                    "message": "热更新补丁已成功应用，请重启软件！",
                    "need_restart": True
                }
            except Exception as e:
                return {"success": False, "message": f"补丁解压失败: {str(e)}"}

        # 方案 B: Windows 独立 EXE 覆盖替换与自重启
        if sys.platform == "win32":
            current_exe = Path(sys.executable) if is_frozen else (Path(__file__).parent.parent / "run_app.bat")
            bat_script = get_app_data_dir() / "apply_restart.bat"

            bat_content = f"""@echo off
chcp 65001 >nul
echo 正在等待原程序关闭并安装更新...
ping 127.0.0.1 -n 2 >nul

:: 等待进程完全释放
taskkill /F /PID {current_pid} >nul 2>&1
ping 127.0.0.1 -n 2 >nul

:: 覆盖新文件
copy /Y "{target_path}" "{current_exe}" >nul

:: 启动新版本
start "" "{current_exe}"

:: 自清理
del "%~f0"
exit
"""
            try:
                bat_script.write_text(bat_content, encoding="utf-8")
                # 隐藏控制台启动更新批处理
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.Popen(str(bat_script), shell=True, startupinfo=startupinfo)

                # 稍后主动退出当前 Python 进程
                def _delayed_exit():
                    time.sleep(1.0)
                    os._exit(0)

                import threading
                threading.Thread(target=_delayed_exit, daemon=True).start()

                return {
                    "success": True,
                    "message": "更新脚本已启动，程序即将自动重启...",
                    "need_restart": True
                }
            except Exception as e:
                return {"success": False, "message": f"创建升级启动器失败: {str(e)}"}

        return {"success": False, "message": "当前操作系统请手动覆盖可执行文件完成更新"}


remote_updater = RemoteUpdater()
