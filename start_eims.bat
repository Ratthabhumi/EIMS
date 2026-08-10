@echo off
title EIMS Core Gateway Server

echo ===================================================
echo   Starting EIMS Database Infrastructure (Docker)...
echo ===================================================
docker compose up -d

echo.
echo ===================================================
echo   Starting EIMS FastAPI Backend Server...
echo ===================================================
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in venv\
    pause
    exit /b 1
)

:: Run the backend server directly using the virtual environment
venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
