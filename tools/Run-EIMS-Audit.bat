@echo off
setlocal EnableExtensions
title EIMS Portable USB Auditor
rem Use an ACL-protected local destination; never bypass company execution policy.
powershell.exe -NoProfile -File "%~dp0Run-Private-Audit.ps1" -PackageRoot "%~dp0." -Export %*
set "EXITCODE=%ERRORLEVEL%"
echo Exit code: %EXITCODE% (0 saved/pass, 1 saved/findings, 3 partial, 2 failed/cancelled)
pause
endlocal & exit /b %EXITCODE%
