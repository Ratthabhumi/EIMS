@echo off
cd /d "%~dp0"
title Disk Sanitization Assistant

if not exist ".venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found.
    echo  Please run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python main.py
