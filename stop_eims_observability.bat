@echo off
title Stop EIMS Observability
cd /d "%~dp0"
echo Stopping Observability profile (volumes preserved)...
call scripts\eims-compose.bat stop-observability
echo Done. Core services are untouched.
pause
