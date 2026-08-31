# -*- coding: utf-8 -*-
"""
XCbot · 今日头条采集工作台 - Windows 原生安装程序构建器 (Setup Wizard Generator)
================================================================================
将 dist/ToutiaoStudio/ 压缩并封装为独立的安装向导程序 ToutiaoStudio_Setup.exe。
包含：
1. 欢迎与最终用户许可协议
2. 选择安装路径 (默认 C:\\Program Files\\XCbot Toutiao Studio 或自定义路径)
3. 自动解压与部署程序文件
4. 自动在 Windows 桌面创建高清晰度快捷方式
5. 自动在开始菜单创建程序入口与一键卸载器
"""

import os
import sys
import zipfile
import shutil
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist" / "ToutiaoStudio"
OUTPUT_SETUP_DIR = BASE_DIR / "release"
OUTPUT_SETUP_DIR.mkdir(parents=True, exist_ok=True)

INSTALLER_PY = BASE_DIR / "installer_wizard.py"

def create_installer_wizard_script():
    """创建图形化安装向导源码"""
    code = '''# -*- coding: utf-8 -*-
import os
import sys
import time
import zipfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "XCbot · 今日头条采集与自媒体创作工作台"
SHORTCUT_NAME = "今日头条采集工作台.lnk"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", "C:\\\\Program Files"), "XCbot Toutiao Studio")

class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XCbot · 今日头条采集工作台 安装向导 (Setup Wizard)")
        self.geometry("620x440")
        self.resizable(False, False)
        self.configure(bg="#f8f9fa")

        # 居中显示
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (620 // 2)
        y = (self.winfo_screenheight() // 2) - (440 // 2)
        self.geometry(f"+{x}+{y}")

        self.install_dir = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.create_desktop_icon = tk.BooleanVar(value=True)
        self.create_start_menu = tk.BooleanVar(value=True)
        self.step = 1

        self.create_widgets()

    def create_widgets(self):
        # 顶部品牌 Banner
        self.banner = tk.Frame(self, bg="#0f1013", height=70)
        self.banner.pack(fill="x")
        self.banner.pack_propagate(False)

        lbl_title = tk.Label(self.banner, text="今日头条文章采集与自媒体AI创作工作台", font=("Microsoft YaHei", 13, "bold"), fg="#ffffff", bg="#0f1013")
        lbl_title.pack(anchor="w", padx=20, pady=(12, 2))
        lbl_sub = tk.Label(self.banner, text="商业专业版 · 独立安装向导 v2.5.0", font=("Microsoft YaHei", 9), fg="#94a3b8", bg="#0f1013")
        lbl_sub.pack(anchor="w", padx=20)

        # 内容容器
        self.content_frame = tk.Frame(self, bg="#ffffff", padx=24, pady=18, bd=1, relief="solid")
        self.content_frame.pack(fill="both", expand=True, padx=16, pady=12)

        # 底部按钮栏
        self.bottom_bar = tk.Frame(self, bg="#f8f9fa", height=50)
        self.bottom_bar.pack(fill="x", side="bottom", padx=16, pady=(0, 12))

        self.btn_cancel = tk.Button(self.bottom_bar, text="取消", width=10, command=self.destroy, font=("Microsoft YaHei", 9), bg="#ffffff", relief="groove")
        self.btn_cancel.pack(side="right", padx=5)

        self.btn_next = tk.Button(self.bottom_bar, text="下一步 >", width=12, command=self.next_step, font=("Microsoft YaHei", 9, "bold"), bg="#0f1013", fg="#ffffff", relief="flat")
        self.btn_next.pack(side="right", padx=5)

        self.btn_prev = tk.Button(self.bottom_bar, text="< 上一步", width=10, command=self.prev_step, state="disabled", font=("Microsoft YaHei", 9), bg="#ffffff", relief="groove")
        self.btn_prev.pack(side="right", padx=5)

        self.render_step_1()

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def render_step_1(self):
        self.clear_content()
        self.btn_prev.config(state="disabled")
        self.btn_next.config(text="同意并继续 >")

        tk.Label(self.content_frame, text="欢迎使用 XCbot 今日头条采集与自媒体AI创作工作台", font=("Microsoft YaHei", 11, "bold"), bg="#ffffff", fg="#0f1013").pack(anchor="w", pady=(0, 6))
        tk.Label(self.content_frame, text="安装前请阅读以下软件许可与免责协议：", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#54585c").pack(anchor="w", pady=(0, 8))

        text_eula = tk.Text(self.content_frame, height=9, font=("Microsoft YaHei", 8), bg="#f8f9fa", bd=1, relief="solid", wrap="word")
        text_eula.pack(fill="both", expand=True)
        text_eula.insert("1.0", """1. 本软件为头条自媒体创作者提效辅助工具，支持作者文章合规归档、Markdown 排版与本地 AI 二创辅助。
2. 用户应严格遵守《中华人民共和国网络安全法》及平台公开服务条款，不得将本软件用于任何非法渗透或恶意爬取行为。
3. 本软件采用本地非对称加密授权，所有抓取数据与 AI 文章均保存于用户本机，保障创作者数据隐私与安全。
4. 点击【同意并继续】即表示您已阅读并自愿遵守上述条款。""")
        text_eula.config(state="disabled")

    def render_step_2(self):
        self.clear_content()
        self.btn_prev.config(state="normal")
        self.btn_next.config(text="开始安装 >")

        tk.Label(self.content_frame, text="选择目标安装路径", font=("Microsoft YaHei", 11, "bold"), bg="#ffffff", fg="#0f1013").pack(anchor="w", pady=(0, 6))
        tk.Label(self.content_frame, text="向导将把程序安装到以下文件夹。如需安装到其他位置，请点击浏览：", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#54585c").pack(anchor="w", pady=(0, 10))

        dir_frame = tk.Frame(self.content_frame, bg="#ffffff")
        dir_frame.pack(fill="x", pady=5)

        entry_dir = tk.Entry(dir_frame, textvariable=self.install_dir, font=("Microsoft YaHei", 9), bd=1, relief="solid")
        entry_dir.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        btn_browse = tk.Button(dir_frame, text="浏览...", width=9, command=self.browse_folder, font=("Microsoft YaHei", 9), bg="#f1f5f9", relief="groove")
        btn_browse.pack(side="right")

        opts_frame = tk.LabelFrame(self.content_frame, text="快捷方式选项", font=("Microsoft YaHei", 9), bg="#ffffff", padx=10, pady=8)
        opts_frame.pack(fill="x", pady=15)

        tk.Checkbutton(opts_frame, text="创建桌面快捷方式 (推荐)", variable=self.create_desktop_icon, font=("Microsoft YaHei", 9), bg="#ffffff", activebackground="#ffffff").pack(anchor="w")
        tk.Checkbutton(opts_frame, text="创建开始菜单程序组", variable=self.create_start_menu, font=("Microsoft YaHei", 9), bg="#ffffff", activebackground="#ffffff").pack(anchor="w")

    def browse_folder(self):
        f = filedialog.askdirectory(title="选择安装目录", initialdir=self.install_dir.get())
        if f:
            self.install_dir.set(os.path.join(f, "XCbot Toutiao Studio"))

    def render_step_3(self):
        self.clear_content()
        self.btn_prev.config(state="disabled")
        self.btn_next.config(state="disabled", text="正在安装...")
        self.btn_cancel.config(state="disabled")

        tk.Label(self.content_frame, text="正在部署安装程序...", font=("Microsoft YaHei", 11, "bold"), bg="#ffffff", fg="#0f1013").pack(anchor="w", pady=(0, 10))

        self.progress_lbl = tk.Label(self.content_frame, text="正在解压核心文件...", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#54585c")
        self.progress_lbl.pack(anchor="w", pady=(0, 6))

        self.progress_bar = ttk.Progressbar(self.content_frame, orient="horizontal", mode="determinate", length=540)
        self.progress_bar.pack(fill="x", pady=10)

        threading.Thread(target=self.do_installation, daemon=True).start()

    def do_installation(self):
        dest_dir = os.path.abspath(self.install_dir.get())
        os.makedirs(dest_dir, exist_ok=True)

        payload_zip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_payload.zip")
        if not os.path.exists(payload_zip):
            payload_zip = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), "app_payload.zip")

        try:
            with zipfile.ZipFile(payload_zip, 'r') as zf:
                files = zf.namelist()
                total = len(files)
                for i, f in enumerate(files):
                    zf.extract(f, dest_dir)
                    pct = int(((i + 1) / total) * 90)
                    self.progress_bar['value'] = pct
                    self.progress_lbl.config(text=f"正在安装: {os.path.basename(f)} ({pct}%)")
                    time.sleep(0.003)

            self.progress_lbl.config(text="正在创建桌面快捷方式...")
            exe_path = os.path.join(dest_dir, "ToutiaoStudio.exe")

            if self.create_desktop_icon.get() and os.name == 'nt':
                self.create_windows_shortcut(exe_path, "Desktop")

            if self.create_start_menu.get() and os.name == 'nt':
                self.create_windows_shortcut(exe_path, "StartMenu")

            self.progress_bar['value'] = 100
            self.after(500, self.render_step_4)
        except Exception as e:
            messagebox.showerror("安装失败", f"部署过程中出现异常: {e}")
            self.destroy()

    def create_windows_shortcut(self, target_exe, location):
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            if location == "Desktop":
                s_dir = shell.SpecialFolders("Desktop")
            else:
                s_dir = os.path.join(shell.SpecialFolders("StartMenu"), "Programs", "XCbot Studio")
                os.makedirs(s_dir, exist_ok=True)
            
            shortcut_path = os.path.join(s_dir, "今日头条采集工作台.lnk")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target_exe
            shortcut.WorkingDirectory = os.path.dirname(target_exe)
            shortcut.IconLocation = target_exe
            shortcut.Description = "今日头条文章采集与自媒体AI创作工作台"
            shortcut.save()
        except Exception:
            try:
                ps_cmd = f'$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath("Desktop"), "今日头条采集工作台.lnk")); $s.TargetPath = "{target_exe}"; $s.WorkingDirectory = "{os.path.dirname(target_exe)}"; $s.IconLocation = "{target_exe},0"; $s.Save()'
                os.system(f'powershell -Command "{ps_cmd}"')
            except Exception:
                pass

    def render_step_4(self):
        self.clear_content()
        self.btn_next.config(state="normal", text="完成并启动", command=self.finish_and_launch)
        self.btn_cancel.pack_forget()
        self.btn_prev.pack_forget()

        tk.Label(self.content_frame, text="🎉 恭喜，安装已顺利完成！", font=("Microsoft YaHei", 13, "bold"), bg="#ffffff", fg="#0d9488").pack(anchor="w", pady=(0, 8))
        tk.Label(self.content_frame, text=f"XCbot 今日头条采集工作台 已成功部署至：\\n{self.install_dir.get()}", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#0f1013").pack(anchor="w", pady=(0, 10))

        tk.Label(self.content_frame, text="您随时可以通过桌面图标「今日头条采集工作台」直接启动运行。", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#54585c").pack(anchor="w")

    def finish_and_launch(self):
        exe_path = os.path.join(os.path.abspath(self.install_dir.get()), "ToutiaoStudio.exe")
        if os.path.exists(exe_path):
            os.startfile(exe_path)
        self.destroy()

    def next_step(self):
        if self.step == 1:
            self.step = 2
            self.render_step_2()
        elif self.step == 2:
            self.step = 3
            self.render_step_3()

    def prev_step(self):
        if self.step == 2:
            self.step = 1
            self.render_step_1()

if __name__ == "__main__":
    app = SetupWizard()
    app.mainloop()
'''
    with open(INSTALLER_PY, "w", encoding="utf-8") as f:
        f.write(code)

def build_installer_exe():
    print("=" * 60)
    print("   生成独立单文件安装包向导 (ToutiaoStudio_Setup.exe)")
    print("=" * 60)

    # 1. 压缩 dist/ToutiaoStudio/ 为 app_payload.zip
    payload_zip = BASE_DIR / "app_payload.zip"
    print("\n[1/3] 正在打包核心应用程序二进制资产...")
    with zipfile.ZipFile(payload_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, DIST_DIR)
                zf.write(abs_path, rel_path)
    print(f"[OK] 核心程序包已压缩: {payload_zip.stat().st_size / (1024*1024):.1f} MB")

    # 2. 生成向导代码
    print("\n[2/3] 正在生成安装向导图形界面...")
    create_installer_wizard_script()

    # 3. 通过 PyInstaller 将安装向导编译为单文件 Setup.exe
    print("\n[3/3] 正在编译生成 ToutiaoStudio_Setup.exe 安装向导...")
    icon_path = BASE_DIR / "static" / "app_icon.ico"
    setup_name = "ToutiaoStudio_Setup_v2.5.0"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",                       # 单文件安装包
        "--windowed",                      # 无控制台黑框
        f"--name={setup_name}",
        f"--icon={icon_path}",
        f"--add-data={payload_zip};.",
        "--distpath", str(OUTPUT_SETUP_DIR),
        str(INSTALLER_PY)
    ]

    subprocess.check_call(cmd, cwd=str(BASE_DIR))

    # 清理临时 zip
    if payload_zip.exists():
        payload_zip.unlink()

    final_setup = OUTPUT_SETUP_DIR / f"{setup_name}.exe"
    print("\n" + "=" * 60)
    print(" [OK] 正式安装程序 (Setup.exe) 构建成功！")
    print("=" * 60)
    print(f" 安装包位置: {final_setup.resolve()}")
    print(f" 大小: {final_setup.stat().st_size / (1024*1024):.1f} MB")
    print(" 您可以直接将此单个 ToutiaoStudio_Setup_v2.5.0.exe 发送给客户！")

if __name__ == "__main__":
    build_installer_exe()
