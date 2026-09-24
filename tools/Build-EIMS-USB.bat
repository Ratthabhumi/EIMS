@echo off
title EIMS Portable USB Auditor Builder
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%Build-EIMS-USB.ps1"

echo.
echo  ============================================================
echo   EIMS Portable USB Auditor Builder
echo  ============================================================
echo.
echo   Steps:
echo     1^) Validate builder script
echo     2^) Build verified package
echo     3^) Select removable drive
echo     4^) Confirm replacement
echo     5^) Copy + verify
echo.
echo   SAFETY:
echo     - The builder NEVER auto-selects a drive
echo     - The builder NEVER formats or repartitions a drive
echo     - Only this directory may be replaced:
echo       ^<selected drive^>:\EIMS_USB_Auditor\
echo.

if not exist "%PS_SCRIPT%" (
    echo  [FAIL] PowerShell builder not found:
    echo         "%PS_SCRIPT%"
    echo.
    endlocal & exit /b 2
)

echo  [1/2] Validating PowerShell builder syntax...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop'; try { [void][ScriptBlock]::Create([IO.File]::ReadAllText('%PS_SCRIPT%')); Write-Host ' [OK] PowerShell syntax valid'; exit 0 } catch { Write-Host (' [FAIL] PowerShell syntax error: ' + $_.Exception.Message); exit 2 }"

if errorlevel 1 (
    set "EXITCODE=%ERRORLEVEL%"
    echo.
    echo  Builder aborted before USB access.
    echo  Exit code: %EXITCODE%
    echo.
    endlocal & exit /b %EXITCODE%
)

echo.
echo  [2/2] Starting EIMS USB builder...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo  ============================================================
    echo   EIMS USB Builder completed successfully.
    echo  ============================================================
) else (
    echo  ============================================================
    echo   EIMS USB Builder failed.
    echo   Exit code: %EXITCODE%
    echo  ============================================================
)

echo.
endlocal & exit /b %EXITCODE%