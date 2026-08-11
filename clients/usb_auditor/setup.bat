@echo off
cd /d "%~dp0"
title USB Auditor Agent Setup

echo ==========================================
echo    EIMS USB Auditor Agent - Setup
echo ==========================================

echo [1/3] Creating Python Virtual Environment...
python -m venv .venv

echo [2/3] Activating Environment...
call .venv\Scripts\activate.bat

echo [3/3] Installing Dependencies...
pip install -r requirements.txt

echo.
echo ==========================================
echo Setup Complete! You can now launch the agent.
echo ==========================================
pause
