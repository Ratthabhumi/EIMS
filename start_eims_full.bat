@echo off
title EIMS Full Development Stack
cd /d "%~dp0"
echo Starting Full Development profile (Core + Observability + Pooler)...
echo Loki is not included (removed from active runtime).
call scripts\eims-compose.bat up-full
if errorlevel 1 (
  echo [ERROR] Full compose up failed.
  pause
  exit /b 1
)
echo.
echo Then start API + Portal with start_eims.bat ^(or run uvicorn/npm separately^).
echo Pooler is available on :6432 but API still defaults to :5432.
pause
