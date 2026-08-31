@echo off
chcp 65001 >nul
title XCbot · 今日头条采集与自媒体创作工作台 - 开发环境一键初始化

echo =======================================================================
echo    XCbot · 今日头条采集与自媒体AI创作工作台 - 二次开发环境初始化
echo =======================================================================
echo.

:: 1. 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] 错误: 未检测到 Python 环境，请确保已安装 Python 3.9+ 并勾选了 Add to PATH。
    pause
    exit /b 1
)

echo [*] 正在检查并安装项目 Python 依赖包 (requirements.txt)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if %errorlevel% neq 0 (
    echo [!] 清华镜像源安装遇到问题，尝试使用官方源重试...
    python -m pip install -r requirements.txt
)

echo.
echo [*] 正在安装与同步 Playwright / Patchright 自动化浏览器内核...
python -m patchright install chromium >nul 2>&1
python -m playwright install chromium >nul 2>&1

echo.
echo [*] 检查 AI 配置文件...
if not exist "data\ai_config.json" (
    if exist "data\ai_config.json.example" (
        copy "data\ai_config.json.example" "data\ai_config.json" >nul
        echo [OK] 已基于模板自动创建 data\ai_config.json，请填入您的 API Key。
    )
)

echo.
echo =======================================================================
echo  [OK] 开发环境准备就绪！您可以按需启动以下模式进行二次开发与调试：
echo =======================================================================
echo  1. 启动 Web API 服务端 (带热重载与 Swagger 文档):
echo     python server.py  (访问 http://127.0.0.1:8765/ 或 /docs)
echo.
echo  2. 启动桌面原生客户端窗口:
echo     python desktop_app.py
echo.
echo  3. 纯命令行爬虫测试:
echo     python run.py --max-articles 5
echo.
echo  4. 离线发卡器签名调试:
echo     python license_tool\generate_license.py
echo.
echo  5. 一键重新打包客户端 EXE:
echo     python build_installer.py
echo =======================================================================
echo.
pause
