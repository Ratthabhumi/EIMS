@echo off
title EIMS Master Startup Script

:: Ensure we are always running from the script's directory
cd /d "%~dp0"

setlocal EnableDelayedExpansion

echo ===================================================
echo   [1/6] Checking Docker availability...
echo ===================================================
docker version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not reachable. Start Docker Desktop and retry.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [2/6] Starting EIMS Infrastructure (Docker)...
echo ===================================================
docker compose up -d --wait --wait-timeout 120
if errorlevel 1 (
    echo [ERROR] 'docker compose up --wait' reported a failure. Current state:
    docker compose ps
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [3/6] Verifying core services are healthy...
echo ===================================================
set "UNHEALTHY=0"
for %%C in (eims-postgres eims-redis eims-minio) do (
    for /f "tokens=*" %%S in ('docker inspect -f "{{.State.Health.Status}}" %%C 2^>nul') do set "HSTATUS=%%S"
    if "!HSTATUS!"=="" (
        for /f "tokens=*" %%S in ('docker inspect -f "{{.State.Status}}" %%C 2^>nul') do set "HSTATUS=running:%%S"
    )
    echo   - %%C : !HSTATUS!
    if not "!HSTATUS!"=="healthy" if not "!HSTATUS!"=="running:running" set "UNHEALTHY=1"
)
if "!UNHEALTHY!"=="1" (
    echo [ERROR] One or more core services are not healthy. Current state:
    docker compose ps
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [4/6] Verifying Python Virtual Environment...
echo ===================================================
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in venv\
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [5/6] Running Database Migrations...
echo ===================================================
venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo [ERROR] Database migration failed. Inspect the output above.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [6/6] Spawning Backend and Frontend Servers...
echo ===================================================
:: Start Backend in a new terminal window
start "EIMS Backend (FastAPI)" cmd /k "venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Bounded poll for backend health (max ~90s) before starting the dashboard
echo Waiting for backend health at http://localhost:8000/api/v1/health ...
set "HEALTHY=0"
for /L %%I in (1,1,30) do (
    venv\Scripts\python.exe -c "import sys,urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health',timeout=3);sys.exit(0)" >nul 2>&1
    if not errorlevel 1 (
        set "HEALTHY=1"
        goto :backend_up
    )
    timeout /t 3 /nobreak >nul
)
:backend_up
if "!HEALTHY!"=="0" (
    echo [ERROR] Backend did not become healthy in time. Check the "EIMS Backend (FastAPI)" window.
    pause
    exit /b 1
)
echo Backend is healthy.

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
