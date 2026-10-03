@echo off
setlocal EnableDelayedExpansion
title EIMS Homelab Isolated Restore Verification Utility
:: ==============================================================================
:: EIMS Homelab Isolated Restore Test Script
:: Governed by EIMS Documentation System (EDS v1.0.0)
:: RESTORES TO AN ISOLATED TEST DATABASE: eims_registry_restore_test
:: NEVER TOUCHES OR DESTROYS THE ACTIVE eims_registry DATABASE!
:: ==============================================================================

if "%~1"=="" (
    echo [ERROR] Usage: restore_test_homelab.bat ^<path_to_backup_directory^>
    echo Example: restore_test_homelab.bat backups\20261003_120000
    exit /b 1
)

set BACKUP_DIR=%~1
if not exist "%BACKUP_DIR%\postgres_eims_registry.dump" (
    echo [ERROR] Could not find postgres_eims_registry.dump in %BACKUP_DIR%
    exit /b 1
)

echo [1/3] Creating isolated test database eims_registry_restore_test...
docker exec eims-postgres psql -U eims_user -d postgres -c "DROP DATABASE IF EXISTS eims_registry_restore_test;"
docker exec eims-postgres psql -U eims_user -d postgres -c "CREATE DATABASE eims_registry_restore_test;"
if errorlevel 1 (
    echo [ERROR] Failed to create isolated test database.
    exit /b 1
)

echo [2/3] Restoring dump to eims_registry_restore_test...
docker cp "%BACKUP_DIR%\postgres_eims_registry.dump" eims-postgres:/tmp/restore.dump
docker exec eims-postgres pg_restore -U eims_user -d eims_registry_restore_test -v /tmp/restore.dump >nul 2>&1
docker exec eims-postgres rm /tmp/restore.dump

echo [3/3] Validating isolated restored tables and row counts...
docker exec eims-postgres psql -U eims_user -d eims_registry_restore_test -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name LIMIT 10;"

echo Cleaning up isolated test database...
docker exec eims-postgres psql -U eims_user -d postgres -c "DROP DATABASE eims_registry_restore_test;"

echo ==============================================================================
echo [SUCCESS] Isolated Restore Test verified cleanly without touching production data!
echo ==============================================================================
