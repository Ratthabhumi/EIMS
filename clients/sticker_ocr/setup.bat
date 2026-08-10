@echo off
cd /d "%~dp0"
title Disk Sanitization Assistant - First Setup
echo.
echo  ============================================
echo   Disk Sanitization Assistant - Setup
echo  ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Please install Python 3.12 or newer.
    pause
    exit /b 1
)

REM Create venv if it does not exist
if not exist ".venv\" (
    echo  Creating virtual environment...
    python -m venv .venv
)

REM Activate and install
echo  Installing dependencies, please wait...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo  ============================================
echo   Setup complete! Run run.bat to start.
echo  ============================================
pause
