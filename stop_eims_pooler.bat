@echo off
title Stop EIMS PgBouncer
cd /d "%~dp0"
echo Stopping Pooler profile (no volumes on PgBouncer)...
call scripts\eims-compose.bat stop-pooler
echo Done. Core services and EIMS_DB_PORT default (:5432) are untouched.
pause
