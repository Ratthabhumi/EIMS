@echo off
title EIMS Master Startup Script

:: Ensure we are always running from the script's directory
cd /d "%~dp0"


echo ===================================================
echo   [1/4] Starting EIMS Infrastructure (Docker)...
echo ===================================================
docker compose up -d

echo.
echo ===================================================
echo   [2/4] Verifying Python Virtual Environment...
echo ===================================================
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in venv\
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [3/4] Running Database Migrations...
echo ===================================================
venv\Scripts\python.exe -m alembic upgrade head

echo.
echo ===================================================
echo   [4/4] Spawning Backend and Frontend Servers...
echo ===================================================
:: Start Backend in a new terminal window
start "EIMS Backend (FastAPI)" cmd /k "venv\Scripts\activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Start Frontend Dashboard in a new terminal window
start "EIMS Dashboard (Next.js)" cmd /k "cd clients\dashboard && npm run dev -- -p 3001"

echo.
echo [SUCCESS] All systems are booting up!
echo - Backend API: http://localhost:8000
echo - EIMS Portal (Next.js): http://localhost:3001
echo - Grafana Metrics: http://localhost:3000
echo.
echo You can safely close this window. The servers are running in the new windows.
pause
