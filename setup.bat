@echo off
setlocal EnableExtensions
title EIMS First-Time Setup
color 0A

REM ============================================================
REM  EIMS First-Time Setup (Windows)
REM  Repository root is derived from this script's location so the
REM  script works from any folder after a clone or a moved copy.
REM ============================================================

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
cd /d "%REPO_ROOT%"

set "FAIL_DETAIL="
set "VENV_DIR=%REPO_ROOT%\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "PY_EXE="

echo ===================================================
echo   [1/4] Checking Prerequisites + Selecting Python
echo ===================================================

REM --- Deterministic Python interpreter selection ------------------------
REM Preferred: Python 3.11 (repository target), then newer installed
REM interpreters that satisfy requires-python >=3.11, finally plain
REM 'python'. Resolution is NOT left to whatever happens to be first
REM in PATH.
call :try_py 3.11
if errorlevel 1 call :try_py 3.12
if errorlevel 1 call :try_py 3.13
if errorlevel 1 call :try_py 3.14
if errorlevel 1 call :try_py 3
if errorlevel 1 call :try_python
if errorlevel 1 (
    set "FAIL_DETAIL=No suitable Python interpreter v3.11 or newer found. Install Python 3.11+ from https://www.python.org/downloads/ and re-run setup.bat."
    goto :fail
)

echo.
echo ===================================================
echo   [2/4] Python Virtual Environment
echo ===================================================

if exist "%VENV_DIR%\" (
    call :validate_venv
    if errorlevel 1 (
        echo.
        echo   [WARN] Existing venv is stale/invalid. This is typical after
        echo          moving or re-cloning the repo to a new folder or PC.
        call :backup_venv
        if errorlevel 1 goto :fail
    ) else (
        echo   Virtual environment is VALID. Reusing it.
        echo   %VENV_PY%
        echo.
    )
)

if not exist "%VENV_DIR%\" (
    echo   Creating virtual environment with %PY_EXE% ...
    "%PY_EXE%" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        set "FAIL_DETAIL=Failed to create a virtual environment using %PY_EXE%."
        goto :fail
    )
    if not exist "%VENV_PY%" (
        set "FAIL_DETAIL=venv creation finished but %VENV_PY% does not exist."
        goto :fail
    )
    echo   Created virtual environment.
    echo   %VENV_PY%
    echo.
)

REM All pip/run actions now use the repository-local venv interpreter.
set "PY_EXE=%VENV_PY%"
echo   Verifying venv interpreter...
"%PY_EXE%" -c "import sys; print('  venv python:', sys.executable); print('  version    :', sys.version.split()[0])"
if errorlevel 1 (
    set "FAIL_DETAIL=The venv interpreter could not run: %PY_EXE%. Delete or back up venv\ and re-run setup.bat."
    goto :fail
)

echo.
echo ===================================================
echo   [3/4] Installing Backend Dependencies
echo ===================================================
if not exist "%REPO_ROOT%\requirements.txt" (
    set "FAIL_DETAIL=requirements.txt not found: %REPO_ROOT%\requirements.txt"
    goto :fail
)
echo   Installing via: %PY_EXE% -m pip install -r requirements.txt
echo.
"%PY_EXE%" -m pip install --disable-pip-version-check -r "%REPO_ROOT%\requirements.txt"
if errorlevel 1 (
    set "FAIL_DETAIL=pip install -r requirements.txt FAILED. Review the pip output above."
    goto :fail
)

echo.
echo   Verifying backend dependencies...
"%PY_EXE%" -m pip show uvicorn >nul 2>&1
if errorlevel 1 (
    set "FAIL_DETAIL=uvicorn is not installed in the venv after install."
    goto :fail
)
"%PY_EXE%" -c "import fastapi, uvicorn; print('  backend imports OK (fastapi, uvicorn)')"
if errorlevel 1 (
    set "FAIL_DETAIL=fastapi/uvicorn import check failed."
    goto :fail
)

echo.
echo ===================================================
echo   [4/4] Installing Frontend Dependencies
echo ===================================================
if not exist "%REPO_ROOT%\clients\dashboard\package.json" (
    set "FAIL_DETAIL=package.json not found: %REPO_ROOT%\clients\dashboard\package.json"
    goto :fail
)
where node >nul 2>&1
if errorlevel 1 (
    set "FAIL_DETAIL=Node.js not found on PATH. Install Node.js LTS and re-run setup.bat."
    goto :fail
)
where npm >nul 2>&1
if errorlevel 1 (
    set "FAIL_DETAIL=npm not found on PATH. Install Node.js LTS and re-run setup.bat."
    goto :fail
)
set "NODE_VER="
set "NPM_VER="
for /f "usebackq delims=" %%i in (`node --version`) do set "NODE_VER=%%i"
for /f "usebackq delims=" %%i in (`npm --version`) do set "NPM_VER=%%i"
echo   node %NODE_VER% / npm %NPM_VER%
echo.
cd /d "%REPO_ROOT%\clients\dashboard"
if exist "%REPO_ROOT%\clients\dashboard\package-lock.json" (
    echo   package-lock.json found - using npm ci for a reproducible install.
    call npm ci
    if errorlevel 1 (
        set "FAIL_DETAIL=npm ci FAILED. Review the npm output above."
        goto :fail
    )
) else (
    echo   No package-lock.json found - using npm install.
    call npm install
    if errorlevel 1 (
        set "FAIL_DETAIL=npm install FAILED. Review the npm output above."
        goto :fail
    )
)
cd /d "%REPO_ROOT%"
if not exist "%REPO_ROOT%\clients\dashboard\node_modules\next\" (
    set "FAIL_DETAIL=Frontend install finished but 'next' is missing from clients\dashboard\node_modules."
    goto :fail
)

echo.
echo ===================================================
echo   [SUCCESS] Setup Completed Successfully!
echo ===================================================
echo   Python venv    : %VENV_PY%
echo   Backend deps   : requirements.txt installed
echo   Frontend deps  : clients\dashboard\node_modules ready
echo.
echo   You can now run start_eims.bat to launch the EIMS platform.
echo.
pause
exit /b 0

REM ============================================================
REM  Subroutines
REM ============================================================

:try_py
set "PY_EXE="
py -%~1 -c "import sys; sys.exit(0)" >nul 2>&1
if errorlevel 1 exit /b 1
py -%~1 -c "import sys; assert sys.version_info >= (3,11), 'too old'; print(sys.executable)" > "%TEMP%\eims_py_select.txt" 2>nul
if errorlevel 1 (
    del "%TEMP%\eims_py_select.txt" >nul 2>&1
    exit /b 1
)
for /f "usebackq delims=" %%i in ("%TEMP%\eims_py_select.txt") do set "PY_EXE=%%i"
del "%TEMP%\eims_py_select.txt" >nul 2>&1
if not defined PY_EXE exit /b 1
echo   Selected Python interpreter: %PY_EXE%
"%PY_EXE%" --version
exit /b 0

:try_python
set "PY_EXE="
python -c "import sys; assert sys.version_info >= (3,11), 'too old'; print(sys.executable)" > "%TEMP%\eims_py_select.txt" 2>nul
if errorlevel 1 exit /b 1
for /f "usebackq delims=" %%i in ("%TEMP%\eims_py_select.txt") do set "PY_EXE=%%i"
del "%TEMP%\eims_py_select.txt" >nul 2>&1
if not defined PY_EXE (
    exit /b 1
)
echo   Selected Python interpreter: %PY_EXE%
"%PY_EXE%" --version
exit /b 0

:validate_venv
if not exist "%VENV_PY%" (
    echo   [DETECT] %VENV_PY% is missing.
    exit /b 1
)
"%VENV_PY%" -c "import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)" >nul 2>&1
if errorlevel 1 (
    echo   [DETECT] venv interpreter does not run as a virtual environment.
    exit /b 1
)
"%VENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo   [DETECT] venv pip is broken - typical after moving the repo between PCs.
    exit /b 1
)
REM Console-script shims embed the venv's absolute path when the venv is
REM created. After moving/re-cloning the repo to a new folder those shims
REM still point at the old location and fail. Probe the pip shim as a
REM moved-repo detector.
if exist "%VENV_DIR%\Scripts\pip.exe" (
    "%VENV_DIR%\Scripts\pip.exe" --version >nul 2>&1
    if errorlevel 1 (
        echo   [DETECT] venv entry-point shims point at a missing path -
        echo           typical after moving the repo between folders or PCs.
        exit /b 1
    )
)
exit /b 0

:backup_venv
set "TS="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "TS=%%i"
if not defined TS (
    set "FAIL_DETAIL=Could not compute a backup timestamp for the stale venv."
    exit /b 1
)
set "BACKUP_DIR=%REPO_ROOT%\venv_backup_%TS%"
echo.
echo   Preserving the stale venv (NOT deleting it):
move /Y "%VENV_DIR%" "%BACKUP_DIR%" >nul 2>&1
if errorlevel 1 (
    set "FAIL_DETAIL=Could not move the stale venv to %BACKUP_DIR%. Close any program that is using venv\ and re-run setup.bat."
    exit /b 1
)
echo   Backup created: %BACKUP_DIR%
exit /b 0

:fail
echo.
echo ===================================================
echo   [ERROR] EIMS Setup FAILED
echo ===================================================
if defined FAIL_DETAIL echo   %FAIL_DETAIL%
echo.
echo   Press any key to close this window (exit code will be 1).
pause
exit /b 1