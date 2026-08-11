@echo off
cd /d "%~dp0"
title EIMS USB Auditor Agent

if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] First time setup detected. Installing dependencies automatically...
    call setup.bat
)

call .venv\Scripts\activate.bat
python main.py --export

pause
