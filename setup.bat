@echo off
title EIMS First-Time Setup
color 0A

REM Determine repository root from script location
set "REPO_ROOT=%~dp0"
REM Remove trailing backslash
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

cd /d "%REPO_ROOT%"

echo ===================================================
echo   [1/3] Setting up Python Virtual Environment...
echo ===================================================
if not exist "%REPO_ROOT%\venv\" (
    echo Creating virtual environment...
    python -m venv "%REPO_ROOT%\venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

echo.
echo ===================================================
echo   [2/3] Installing Python Dependencies...
echo ===================================================
if not exist "%REPO_ROOT%\requirements.txt" (
    echo [ERROR] requirements.txt not found in %REPO_ROOT%
    exit /b 1
)
call "%REPO_ROOT%\venv\Scripts\pip" install -r "%REPO_ROOT%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies
    exit /b 1
)

echo.
echo ===================================================
echo   [3/3] Installing Frontend Dependencies...
echo ===================================================
if not exist "%REPO_ROOT%\clients\dashboard\package.json" (
    echo [ERROR] package.json not found in %REPO_ROOT%\clients\dashboard
    exit /b 1
)
cd /d "%REPO_ROOT%\clients\dashboard"
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies
    exit /b 1
)
cd /d "%REPO_ROOT%"

echo.
echo ===================================================
echo   [SUCCESS] Setup Completed Successfully!
echo ===================================================
echo You can now run start_eims.bat to launch the EIMS platform.
echo.
pause
