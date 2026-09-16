@echo off
title EIMS Portable USB Auditor
setlocal EnableExtensions
echo.
echo  ============================================================
echo   EIMS Portable USB Auditor - offline evidence collector
echo  ============================================================
echo.
echo   This machine is the AUDIT TARGET. Evidence is written to
echo   this USB drive only. No network access is required.
echo   Best results: Run as Administrator (Security/BitLocker data).
echo.
rem Every portable run defaults to OFFLINE-SAFE behavior:
rem the local JSON report always completes and is never lost.
set "EIMS_AUTO_SYNC=false"
rem Optional overrides - uncomment to redirect evidence/logs elsewhere:
rem set "EIMS_REPORTS_DIR=%~dp0evidence\reports"
rem set "EIMS_LOGS_DIR=%~dp0evidence\logs"
rem Optional: pass --export to also generate Summary.xlsx from reports:
rem "%~dp0runtime\python\python.exe" -B "%~dp0main.py" --export
"%~dp0runtime\python\python.exe" -B "%~dp0main.py" %*
set "EXITCODE=%ERRORLEVEL%"
echo.
echo  ============================================================
echo   Audit finished. Exit code: %EXITCODE%
echo   Reports: %~dp0reports
echo   Logs   : %~dp0logs
echo   Remove this USB drive and import evidence into EIMS.
echo  ============================================================
echo.
pause
endlocal & exit /b %EXITCODE%