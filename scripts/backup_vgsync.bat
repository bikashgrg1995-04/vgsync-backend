@echo off
title VGSync Safe DB Backup (dumpdata)

:: ---- CONFIG ----
set PROJECT_DIR=C:\Users\ADMIN\vgsync-backend
set BACKUP_DIR=C:\Users\ADMIN\vgsync-backend\backups
set PYTHON=C:\Users\ADMIN\vgsync-backend\env\Scripts\python.exe

:: ---- VALIDATION ----
if not exist "%PROJECT_DIR%\manage.py" (
    echo ❌ manage.py not found in PROJECT_DIR
    pause
    exit /b
)

if not exist "%PYTHON%" (
    echo ❌ Python not found at:
    echo %PYTHON%
    pause
    exit /b
)

:: ---- DATE ----
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DATETIME=%%I
set DATESTAMP=%DATETIME:~0,4%-%DATETIME:~4,2%-%DATETIME:~6,2%

set TODAY_BACKUP=%BACKUP_DIR%\%DATESTAMP%
if not exist "%TODAY_BACKUP%" mkdir "%TODAY_BACKUP%"

:: ---- BACKUP ----
echo Backing up database using dumpdata...
cd /d "%PROJECT_DIR%"

"%PYTHON%" manage.py dumpdata --indent 2 ^
 --exclude auth.permission ^
 --exclude contenttypes ^
 > "%TODAY_BACKUP%\data.json"

if errorlevel 1 (
    echo ❌ DB dump failed!
) else (
    echo ✅ DB dump completed successfully
)

pause
