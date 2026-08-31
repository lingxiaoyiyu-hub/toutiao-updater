# -*- coding: utf-8 -*-
"""
XCbot · 今日头条采集工作台 - Windows 原生标准卸载程序 (Uninstaller)
===============================================================
1. 弹出图形化卸载确认对话框
2. 安全终止正在运行的 ToutiaoStudio 进程
3. 清理桌面快捷方式与开始菜单快捷方式
4. 从 Windows 注册表 (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall) 移除卸载信息
5. 自删除安装目录中的全部文件与文件夹
"""

import os
import sys
import time
import subprocess
import tkinter as tk
from tkinter import messagebox

APP_NAME = "XCbot · 今日头条文章采集与自媒体AI创作工作台"
REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\XCbotToutiaoStudio"

def remove_registry_entry():
    if os.name != 'nt':
        return
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH)
    except Exception:
        pass

def remove_shortcuts():
    if os.name != 'nt':
        return
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        # 桌面快捷方式
        desktop_dir = shell.SpecialFolders("Desktop")
        desktop_lnk = os.path.join(desktop_dir, "今日头条采集工作台.lnk")
        if os.path.exists(desktop_lnk):
            os.remove(desktop_lnk)

        # 开始菜单快捷方式
        start_dir = os.path.join(shell.SpecialFolders("StartMenu"), "Programs", "XCbot Studio")
        if os.path.exists(start_dir):
            import shutil
            shutil.rmtree(start_dir, ignore_errors=True)
    except Exception:
        try:
            ps_cmd = '$ws = New-Object -ComObject WScript.Shell; $d = [System.IO.Path]::Combine([Environment]::GetFolderPath("Desktop"), "今日头条采集工作台.lnk"); if (Test-Path $d) { Remove-Item $d -Force }'
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        except Exception:
            pass

def kill_running_process():
    if os.name == 'nt':
        subprocess.run(["taskkill", "/F", "/IM", "ToutiaoStudio.exe"], capture_output=True)

def self_delete_and_exit(install_dir):
    temp_dir = os.environ.get("TEMP", os.path.dirname(install_dir))
    bat_path = os.path.join(temp_dir, f"xc_uninstall_{int(time.time())}.bat")
    
    # 编写自清理批处理
    bat_content = f"""@echo off
chcp 65001 >nul
timeout /t 1 /nobreak >nul
taskkill /F /IM ToutiaoStudio.exe >nul 2>&1
timeout /t 1 /nobreak >nul
rd /s /q "{install_dir}" >nul 2>&1
del "%~f0" >nul 2>&1
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    
    # 异步唤起批处理自删除
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        close_fds=True
    )
    sys.exit(0)

def main():
    root = tk.Tk()
    root.withdraw()

    # 静默卸载模式判断 (/S 或 /silent)
    is_silent = any(arg.upper() in ["/S", "/SILENT", "-S"] for arg in sys.argv)

    if not is_silent:
        confirmed = messagebox.askyesno(
            "卸载确认",
            f"您确定要从这台电脑中彻底卸载【{APP_NAME}】吗？\n\n卸载后将移除所有程序组件与快捷方式。"
        )
        if not confirmed:
            sys.exit(0)

    install_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. 结束运行进程
    kill_running_process()

    # 2. 移除注册表项
    remove_registry_entry()

    # 3. 移除快捷方式
    remove_shortcuts()

    if not is_silent:
        messagebox.showinfo("卸载完成", f"【{APP_NAME}】已成功从您的计算机中完全卸载！")

    # 4. 异步清理目录
    self_delete_and_exit(install_dir)

if __name__ == "__main__":
    main()
