@echo off
:: ================================
:: VGSync Daily Backup Script
:: ================================
:: Author: Bikash Gurung
:: Description: Backs up database + media folder daily
:: ================================

:: ---- CONFIG ----
set PROJECT_DIR=D:\Projects\django\vgsync-backend
set BACKUP_DIR=D:\Projects\django\vgsync-backend\backups
set DATESTAMP=%date:~-4%-%date:~4,2%-%date:~7,2%
set KEEP_DAYS=30

echo ======================================
echo Starting VGSync Backup - %DATESTAMP%
echo ======================================

:: ---- CREATE BACKUP FOLDER ----
if not exist "%BACKUP_DIR%\%DATESTAMP%" mkdir "%BACKUP_DIR%\%DATESTAMP%"

:: ---- BACKUP DATABASE ----
echo Backing up database...
copy "%PROJECT_DIR%\db.sqlite3" "%BACKUP_DIR%\%DATESTAMP%\db_backup.sqlite3" >nul

:: ---- BACKUP MEDIA ----
if exist "%PROJECT_DIR%\media" (
    echo Backing up media files...
    xcopy "%PROJECT_DIR%\media" "%BACKUP_DIR%\%DATESTAMP%\media" /E /I /Y >nul
) else (
    echo No media folder found, skipping media backup.
)

:: ---- CLEANUP OLD BACKUPS ----
echo Cleaning up backups older than %KEEP_DAYS% days...
set DELETED=0
for /f "delims=" %%F in ('forfiles /p "%BACKUP_DIR%" /d -%KEEP_DAYS% 2^>nul') do (
    echo Deleting %%F
    rd /s /q "%%F"
    set DELETED=1
)
if %DELETED%==0 echo No older files to delete.

echo Backup completed successfully on %DATESTAMP%.
echo Files saved to: %BACKUP_DIR%\%DATESTAMP%
echo ======================================
pause
