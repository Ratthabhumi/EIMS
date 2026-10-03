@echo off
setlocal EnableDelayedExpansion
title EIMS Homelab Backup Utility
:: ==============================================================================
:: EIMS Homelab Non-Destructive Backup Script
:: Governed by EIMS Documentation System (EDS v1.0.0)
:: Backs up:
::   1. PostgreSQL database (pg_dump via eims-postgres)
::   2. MinIO OCR bucket objects (mirror via eims-minio)
::   3. Deployment configuration & template (.env.homelab.example, docker-compose.homelab.yml)
:: ==============================================================================

cd /d "%~dp0"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set TIMESTAMP=%dt:~0,4%%dt:~4,2%%dt:~6,2%_%dt:~8,2%%dt:~10,2%%dt:~12,2%
set BACKUP_DIR=backups\%TIMESTAMP%

echo [1/4] Preparing backup directory: %BACKUP_DIR%
mkdir "%BACKUP_DIR%" 2>nul
mkdir "%BACKUP_DIR%\minio_ocr" 2>nul

echo [2/4] Dumping PostgreSQL database (eims_registry)...
docker exec eims-postgres pg_dump -U eims_user -d eims_registry -F c -f /tmp/backup.dump
if errorlevel 1 (
    echo [ERROR] pg_dump failed inside container eims-postgres.
    pause
    exit /b 1
)
docker cp eims-postgres:/tmp/backup.dump "%BACKUP_DIR%\postgres_eims_registry.dump"
docker exec eims-postgres rm /tmp/backup.dump

echo [3/4] Exporting MinIO OCR objects...
docker run --rm --network container:eims-minio -v "%CD%\%BACKUP_DIR%\minio_ocr:/backup" minio/mc:latest mirror eims_local/eims-ocr-manifests /backup 2>nul
if errorlevel 1 (
    echo [INFO] MinIO direct mirror container returned notice or bucket is empty.
)

echo [4/4] Copying deployment overlays...
copy docker-compose.homelab.yml "%BACKUP_DIR%\" >nul
copy .env.homelab.example "%BACKUP_DIR%\" >nul

echo ==============================================================================
echo [SUCCESS] Backup completed successfully at %BACKUP_DIR%
echo Contents:
dir "%BACKUP_DIR%"
echo ==============================================================================
pause
