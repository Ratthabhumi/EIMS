@echo off
title EIMS PgBouncer Profile
cd /d "%~dp0"
echo Starting Pooler profile (PgBouncer :6432)...
echo NOTE: Core API still defaults to PostgreSQL :5432 via EIMS_DB_PORT.
echo Set EIMS_DB_PORT=6432 only when you intentionally want PgBouncer.
call scripts\eims-compose.bat up-pooler
if errorlevel 1 (
  echo [ERROR] Failed to start pooler profile.
  pause
  exit /b 1
)
echo PgBouncer: 127.0.0.1:6432 -^> postgres_db:5432
echo Stop with: stop_eims_pooler.bat
pause
