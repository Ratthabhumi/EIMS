@echo off
title EIMS Observability Profile
cd /d "%~dp0"
echo Starting Observability profile (Prometheus + Grafana)...
call scripts\eims-compose.bat up-observability
if errorlevel 1 (
  echo [ERROR] Failed to start observability profile.
  pause
  exit /b 1
)
echo.
echo Prometheus: http://127.0.0.1:9090
echo Grafana:    http://127.0.0.1:3000
echo Core API /metrics scrape target must be running on :8000.
echo Stop with: stop_eims_observability.bat
pause
