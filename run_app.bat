@echo off
title Toutiao Scraper Studio - App Launcher
cd /d "%~dp0"

python server.py
if errorlevel 1 (
    echo.
    echo ========================================================
    echo Error: Failed to start server.
    echo Please ensure dependencies are installed:
    echo pip install -r requirements.txt
    echo ========================================================
    echo.
    pause
)
