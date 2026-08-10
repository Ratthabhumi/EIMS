@echo off
cd /d "%~dp0"
title Building FolderCreator.exe (Obfuscated & Encrypted)
echo.
echo  ============================================
echo   Building FolderCreator.exe (PyArmor Obfuscated)
echo  ============================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo  [ERROR] Run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
taskkill /f /im FolderCreator.exe >nul 2>&1
pip install pyarmor pyinstaller >nul

echo  [1/4] Obfuscating source code with PyArmor...
if exist "build_obf" rmdir /s /q "build_obf"
python -m pyarmor.cli gen -O build_obf -r main.py app/

if not exist "build_obf\main.py" (
    echo  [ERROR] PyArmor obfuscation failed.
    pause
    exit /b 1
)

echo  [2/4] Compiling executable with PyInstaller...
pyinstaller ^
  --noconfirm ^
  --onedir ^
  --windowed ^
  --name "FolderCreator" ^
  --paths "build_obf" ^
  --add-data "config.json;." ^
  --add-data "build_obf\app;app" ^
  --add-data "build_obf\pyarmor_runtime_000000;pyarmor_runtime_000000" ^
  --hidden-import "app" ^
  --hidden-import "app.config" ^
  --hidden-import "app.constants" ^
  --hidden-import "app.models.job" ^
  --hidden-import "app.models.result" ^
  --hidden-import "app.services.crop_service" ^
  --hidden-import "app.services.folder_service" ^
  --hidden-import "app.services.logger_service" ^
  --hidden-import "app.services.notifier" ^
  --hidden-import "app.services.ocr_engine" ^
  --hidden-import "app.services.queue_service" ^
  --hidden-import "app.services.usb_monitor" ^
  --hidden-import "app.services.validator" ^
  --hidden-import "app.services.watch_service" ^
  --hidden-import "app.viewmodels.app_viewmodel" ^
  --hidden-import "app.views.dashboard_tab" ^
  --hidden-import "app.views.history_tab" ^
  --hidden-import "app.views.large_display_window" ^
  --hidden-import "app.views.main_window" ^
  --hidden-import "app.views.settings_tab" ^
  --hidden-import "rapidocr_onnxruntime" ^
  --hidden-import "onnxruntime" ^
  --hidden-import "cv2" ^
  --hidden-import "PIL" ^
  --hidden-import "customtkinter" ^
  --hidden-import "watchdog.observers.winapi" ^
  --hidden-import "winotify" ^
  --collect-all "rapidocr_onnxruntime" ^
  --collect-all "onnxruntime" ^
  --collect-all "customtkinter" ^
  build_obf\main.py

echo  [3/4] Setting up distribution folders and zipping package...
if exist "dist\FolderCreator\" (
    mkdir "dist\FolderCreator\Sticker\Processed" >nul 2>&1
    mkdir "dist\FolderCreator\Sticker\Failed" >nul 2>&1
    mkdir "dist\FolderCreator\Logs" >nul 2>&1
    python -c "import shutil; shutil.make_archive('FolderCreator', 'zip', 'dist', 'FolderCreator')" >nul 2>&1
)

echo  [4/4] Deploying cleanly to C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator...
if exist "dist\FolderCreator\FolderCreator.exe" (
    taskkill /f /im FolderCreator.exe >nul 2>&1
    if not exist "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator" mkdir "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator"
    copy /y "dist\FolderCreator\FolderCreator.exe" "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\FolderCreator.exe" >nul
    if exist "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\_internal" rmdir /s /q "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\_internal"
    xcopy /e /i /q /y "dist\FolderCreator\_internal" "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\_internal" >nul
    mkdir "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\Sticker\Processed" >nul 2>&1
    mkdir "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\Sticker\Failed" >nul 2>&1
    mkdir "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\Logs" >nul 2>&1
    if exist "FolderCreator.zip" copy /y "FolderCreator.zip" "C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\FolderCreator.zip" >nul
    echo  [SUCCESS] Deployed new FolderCreator.exe cleanly! (User data in Sticker and Logs intact)
)

echo.
echo  ============================================
echo   Done! Executable deployed to:
echo   C:\Users\Ratthabhumi\Desktop\CO-OP_Project\FolderCreator\
echo  ============================================
pause
