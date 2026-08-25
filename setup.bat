@echo off
title EIMS First-Time Setup
color 0A

echo ===================================================
echo   [1/3] Setting up Python Virtual Environment...
echo ===================================================
if not exist venv\ (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

echo.
echo ===================================================
echo   [2/3] Installing Python Dependencies...
echo ===================================================
call .\venv\Scripts\pip install -r requirements.txt

echo.
echo ===================================================
echo   [3/3] Installing Frontend Dependencies...
echo ===================================================
cd clients\dashboard
call npm install
cd ..\..

echo.
echo ===================================================
echo   [SUCCESS] Setup Completed Successfully!
echo ===================================================
echo You can now run start_eims.bat to launch the EIMS platform.
echo.
pause
