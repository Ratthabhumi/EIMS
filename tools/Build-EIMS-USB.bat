@echo off
title EIMS Portable USB Auditor Builder
setlocal EnableExtensions
echo.
echo  ============================================================
echo   EIMS Portable USB Auditor Builder
echo  ============================================================
echo.
echo   Steps: 1) build verified package  2) select removable drive
echo          3) confirm replacement   4) copy + verify
echo.
echo   The builder NEVER auto-selects a drive and never formats.
echo   Only this directory may be replaced:
echo     ^<selected drive^>:\EIMS_USB_Auditor\
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-EIMS-USB.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
echo  Builder exit code: %EXITCODE%
echo.
endlocal & exit /b %EXITCODE%