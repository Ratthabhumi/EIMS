@echo off
powershell.exe -NoProfile -File "%~dp0tools\handover\Clone-TwoUsb.ps1" -Kind EIMS_HANDOVER %*
exit /b %ERRORLEVEL%
