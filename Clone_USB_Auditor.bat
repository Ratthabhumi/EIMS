@echo off
powershell.exe -NoProfile -File "%~dp0tools\handover\Clone-TwoUsb.ps1" -Kind USB_AUDITOR %*
exit /b %ERRORLEVEL%
