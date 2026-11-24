@echo off
:: Shared Compose helpers for EIMS local profiles.
:: Usage: call scripts\eims-compose.bat <command>
setlocal
cd /d "%~dp0\.."

if "%~1"=="" (
  echo Usage: eims-compose.bat up-core^|up-observability^|stop-observability^|up-pooler^|stop-pooler^|up-full^|status
  exit /b 1
)

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"

if /I "%~1"=="up-core" (
  :: Local Core + Observability (Grafana/Prometheus) by default; PgBouncer stays optional.
  docker compose up -d postgres_db redis_cache minio_s3 minio_setup prometheus grafana
  if errorlevel 1 exit /b 1
  "%PY%" scripts\set_active_profiles.py --observability 1
  exit /b %errorlevel%
)

if /I "%~1"=="up-observability" (
  docker compose --profile observability up -d prometheus grafana
  if errorlevel 1 exit /b 1
  "%PY%" scripts\set_active_profiles.py --observability 1
  exit /b %errorlevel%
)

if /I "%~1"=="stop-observability" (
  docker compose stop prometheus grafana 2>nul
  "%PY%" scripts\set_active_profiles.py --observability 0
  exit /b 0
)

if /I "%~1"=="up-pooler" (
  docker compose --profile pooler up -d pgbouncer
  if errorlevel 1 exit /b 1
  "%PY%" scripts\set_active_profiles.py --pooler 1
  exit /b %errorlevel%
)

if /I "%~1"=="stop-pooler" (
  docker compose stop pgbouncer 2>nul
  "%PY%" scripts\set_active_profiles.py --pooler 0
  exit /b 0
)

if /I "%~1"=="up-full" (
  docker compose --profile full up -d
  if errorlevel 1 exit /b 1
  "%PY%" scripts\set_active_profiles.py --observability 1 --pooler 1
  exit /b %errorlevel%
)

if /I "%~1"=="status" (
  docker compose ps -a
  if exist "deployments\local\active-profiles.env" type "deployments\local\active-profiles.env"
  exit /b 0
)

echo Unknown command: %~1
exit /b 1
