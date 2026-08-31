@echo off
chcp 65001 >nul
title XCbot · 今日头条采集工作台 - 一键推送到 GitHub

echo =======================================================================
echo    XCbot · 今日头条采集与AI创作工作台 - 一键推送到 GitHub 仓库
echo =======================================================================
echo.
echo [说明] 本脚本将帮助您一键将最新源码及 version.json 推送到您的 GitHub 仓库中。
echo.

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] 错误: 未检测到 Git 工具，请先安装 Git。
    pause
    exit /b 1
)

:: 检查当前是否有 remote
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo 请输入您的 GitHub 仓库地址 (例如 https://github.com/您的用户名/toutiao-studio.git):
    set /p REPO_URL="> "
    if "%REPO_URL%"=="" (
        echo [X] 仓库地址不能为空！
        pause
        exit /b 1
    )
    git remote add origin %REPO_URL%
) else (
    echo [*] 当前已关联远程仓库:
    git remote -v
    echo.
)

echo [*] 正在暂存并提交本地修改...
git add -A
git commit -m "feat: update to latest version v2.5.0 with updater & abort crawl" >nul 2>&1

echo.
echo [*] 正在推送至 GitHub main 分支...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo =======================================================================
    echo  [OK] 代码与版本清单已成功推送到 GitHub！
    echo       全网用户现在可通过云端检测到您的最新更新！
    echo =======================================================================
) else (
    echo.
    echo [!] 推送遇到问题，可能是网络波动或未登录 GitHub 凭据，请根据终端提示重试。
)

echo.
pause
