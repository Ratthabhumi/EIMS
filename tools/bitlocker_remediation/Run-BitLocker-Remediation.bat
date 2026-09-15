@echo off
rem ============================================================
rem  EIMS BitLocker Remediation Assistant - launcher
rem  PLAN-ONLY by default. Pass -Apply for authorized changes.
rem ============================================================
setlocal
cd /d "%~dp0"
title EIMS BitLocker Remediation (Plan-Only by default)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Remediate-BitLocker.ps1" %*

set "RC=%ERRORLEVEL%"
echo.
if %RC% EQU 0 (
    echo [OK] BitLocker remediation assistant finished (exit code 0).
) else (
    echo [FAIL] BitLocker remediation assistant finished with exit code %RC%.
)
echo.
pause
endlocal