@echo off
title Stop EIMS Optional Profiles
cd /d "%~dp0"
echo Stopping Observability + Pooler (Core + volumes preserved; no -v)...
call scripts\eims-compose.bat stop-observability
call scripts\eims-compose.bat stop-pooler
echo Done.
pause
