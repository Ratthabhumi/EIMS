@echo off
title EIMS Master Startup Script - Local Core

:: Ensure we are always running from the script's directory
cd /d "%~dp0"

setlocal EnableDelayedExpansion

echo ===================================================
echo   [1/7] Checking Docker availability...
echo ===================================================
docker version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not reachable. Start Docker Desktop and retry.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [2/7] Clearing EIMS ports before start...
echo   Host: 8000, 3001  ^|  Docker republish: 5432,6379,9000,9001,9090,3000
echo ===================================================
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\clear_local_ports.py
) else (
    python scripts\clear_local_ports.py
)
if errorlevel 1 (
    echo [WARN] Port clear reported an error; continuing with compose up.
)
timeout /t 2 /nobreak >nul

echo.
echo ===================================================
echo   [3/7] Starting EIMS Local Core + Observability...
echo   (Postgres, Redis, MinIO, Prometheus, Grafana)
echo   Optional: PgBouncer is NOT started here.
echo ===================================================
call scripts\eims-compose.bat up-core
if errorlevel 1 (
    echo [ERROR] Core compose up failed. Current state:
    docker compose ps
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [4/7] Verifying core services and setup...
echo ===================================================
echo Polling core infrastructure (Postgres, Redis, MinIO)...
set "CORE_OK=0"
for /L %%I in (1,1,30) do (
    set "UNHEALTHY=0"
    for %%C in (eims-postgres eims-redis eims-minio) do (
        set "HSTATUS="
        for /f "tokens=*" %%S in ('docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" %%C 2^>nul') do set "HSTATUS=%%S"
        if not "!HSTATUS!"=="healthy" if not "!HSTATUS!"=="running" set "UNHEALTHY=1"
    )
    if "!UNHEALTHY!"=="0" (
        set "CORE_OK=1"
        goto :core_ready
    )
    timeout /t 2 /nobreak >nul
)
:core_ready
if "!CORE_OK!"=="0" (
    echo [ERROR] Core services did not become healthy in time. Current state:
    docker compose ps
    pause
    exit /b 1
)
for %%C in (eims-postgres eims-redis eims-minio) do (
    set "HSTATUS="
    for /f "tokens=*" %%S in ('docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" %%C 2^>nul') do set "HSTATUS=%%S"
    echo   - %%C : !HSTATUS!
)

echo Checking one-shot container eims-minio-setup...
set "SETUP_OK=0"
for /L %%I in (1,1,20) do (
    set "HSTATUS="
    set "SETUP_EXIT="
    for /f "tokens=*" %%S in ('docker inspect -f "{{.State.Status}}" eims-minio-setup 2^>nul') do set "HSTATUS=%%S"
    for /f "tokens=*" %%S in ('docker inspect -f "{{.State.ExitCode}}" eims-minio-setup 2^>nul') do set "SETUP_EXIT=%%S"
    if "!HSTATUS!"=="exited" (
        if "!SETUP_EXIT!"=="0" (
            set "SETUP_OK=1"
            echo   - eims-minio-setup : exited (exit code 0)
            goto :setup_done
        ) else (
            echo [ERROR] eims-minio-setup failed with exit code !SETUP_EXIT!.
            docker logs eims-minio-setup
            pause
            exit /b 1
        )
    )
    timeout /t 2 /nobreak >nul
)
:setup_done
if "!SETUP_OK!"=="0" (
    echo [ERROR] eims-minio-setup did not exit cleanly in time. Status: !HSTATUS!
    docker logs eims-minio-setup
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [5/7] Verifying Python Virtual Environment...
echo ===================================================
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in venv\
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   [6/7] Running Database Migrations...
echo ===================================================
:: Docker Desktop can leave :5432 published while asyncpg still gets connection_lost until Postgres restarts.
echo Probing PostgreSQL on 127.0.0.1:5432...
venv\Scripts\python.exe scripts\probe_local_postgres.py >nul 2>&1
if errorlevel 1 (
    echo [WARN] Postgres :5432 not accepting asyncpg yet. Restarting eims-postgres...
    docker restart eims-postgres >nul
    timeout /t 8 /nobreak >nul
    venv\Scripts\python.exe scripts\probe_local_postgres.py
    if errorlevel 1 (
        echo [ERROR] PostgreSQL still unreachable on 127.0.0.1:5432 after restart.
        pause
        exit /b 1
    )
)
venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
    echo [ERROR] Database migration failed. Inspect the output above.
    echo Tip: docker restart eims-postgres  then re-run start_eims.bat
    pause
    exit /b 1
)

echo Probing Redis on 127.0.0.1:6379...
venv\Scripts\python.exe scripts\probe_local_redis.py >nul 2>&1
if errorlevel 1 (
    echo [WARN] Redis :6379 not accepting clients yet. Restarting eims-redis...
    docker restart eims-redis >nul
    timeout /t 5 /nobreak >nul
    venv\Scripts\python.exe scripts\probe_local_redis.py
    if errorlevel 1 (
        echo [ERROR] Redis still unreachable on 127.0.0.1:6379 after restart.
        pause
        exit /b 1
    )
)

echo Probing MinIO on 127.0.0.1:9000...
venv\Scripts\python.exe scripts\probe_local_minio.py >nul 2>&1
if errorlevel 1 (
    echo [WARN] MinIO :9000 not accepting clients yet. Restarting eims-minio...
    docker restart eims-minio >nul
    timeout /t 6 /nobreak >nul
    venv\Scripts\python.exe scripts\probe_local_minio.py
    if errorlevel 1 (
        echo [ERROR] MinIO still unreachable on 127.0.0.1:9000 after restart.
        pause
        exit /b 1
    )
)

echo Probing Prometheus :9090 + Grafana :3000...
venv\Scripts\python.exe scripts\probe_local_observability.py >nul 2>&1
if errorlevel 1 (
    echo [WARN] Observability ports not accepting clients yet. Restarting eims-prometheus eims-grafana...
    docker restart eims-prometheus eims-grafana >nul
    timeout /t 8 /nobreak >nul
    venv\Scripts\python.exe scripts\probe_local_observability.py
    if errorlevel 1 (
        echo [ERROR] Prometheus/Grafana still unreachable on 127.0.0.1 after restart.
        pause
        exit /b 1
    )
)

echo.
echo ===================================================
echo   [7/7] Spawning Backend and Frontend Servers...
echo ===================================================
:: Host ports already cleared in step 2; re-check 8000/3001 in case something reclaimed them.
for %%Q in (8000 3001) do (
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%%Q .*LISTENING"') do (
        echo [WARN] Port %%Q in use by PID %%P — stopping stale process...
        taskkill /PID %%P /F >nul 2>&1
    )
)
:: Loopback-only for local-first; containers still use the Compose network.
start "EIMS Backend (FastAPI)" cmd /k "venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

:: Bounded poll for backend readiness (max ~90s) before starting the dashboard.
:: Use /ready (not /health): soft-deps and optional tiers may return HTTP 503 DEGRADED
:: while the API is still usable; urllib treats 503 as failure and caused boot loops/flicker.
echo Waiting for backend readiness at http://127.0.0.1:8000/api/v1/ready ...
set "HEALTHY=0"
for /L %%I in (1,1,30) do (
    venv\Scripts\python.exe -c "import sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready',timeout=3); sys.exit(0 if 200<=r.status<300 else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "HEALTHY=1"
        goto :backend_up
    )
    timeout /t 3 /nobreak >nul
)
:backend_up
if "!HEALTHY!"=="0" (
    echo [ERROR] Backend did not become ready in time. Check the "EIMS Backend (FastAPI)" window.
    pause
    exit /b 1
)
echo Backend is ready.

:: Start Frontend Dashboard (loopback) in a new terminal window
start "EIMS Dashboard (Next.js)" cmd /k "cd clients\dashboard && npm run dev -- -H 127.0.0.1 -p 3001"

echo Waiting for Portal at http://127.0.0.1:3001 ...
set "PORTAL_OK=0"
for /L %%I in (1,1,40) do (
    venv\Scripts\python.exe -c "import sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:3001',timeout=3); sys.exit(0 if 200<=r.status<500 else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PORTAL_OK=1"
        goto :portal_up
    )
    timeout /t 3 /nobreak >nul
)
:portal_up
if "!PORTAL_OK!"=="0" (
    echo [WARN] Portal did not respond in time. Check the "EIMS Dashboard (Next.js)" window.
) else (
    echo Portal is available.
)

echo.
echo [SUCCESS] EIMS Local Core + Observability is up.
echo   PostgreSQL : 127.0.0.1:5432
echo   Redis      : 127.0.0.1:6379
echo   MinIO      : 127.0.0.1:9000  (console :9001)
echo   Prometheus : http://127.0.0.1:9090
echo   Grafana    : http://127.0.0.1:3000
echo   Core API   : http://127.0.0.1:8000
echo   Portal     : http://127.0.0.1:3001
echo.
echo Optional:
echo   stop_eims_observability.bat   -- stop Grafana/Prometheus only
echo   start_eims_pooler.bat         -- PgBouncer :6432 (API still defaults to :5432)
echo See docs\operations\LOCAL_OPERATIONS_RUNBOOK.md
echo.
echo You can safely close this window. The servers are running in the new windows.
pause
