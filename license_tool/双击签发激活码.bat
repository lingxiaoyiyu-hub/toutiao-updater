@echo off
title Toutiao Scraper Studio - License Issuer
cd /d "%~dp0"

python generate_license.py
if errorlevel 1 (
    echo.
    echo ========================================================
    echo Error: Failed to run license generator.
    echo Please install dependencies: pip install cryptography
    echo ========================================================
    echo.
    pause
)
