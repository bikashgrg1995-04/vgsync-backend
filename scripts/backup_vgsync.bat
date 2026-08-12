@echo off
chcp 65001 >nul
title VGSync Safe DB Backup (dumpdata)

:: ---- CONFIG ----
set PROJECT_DIR=D:\vgsync\vgsync-backend
set BACKUP_DIR=D:\vgsync\vgsync-backend\backups
set PYTHON=D:\vgsync\vgsync-backend\venv\Scripts\python.exe

:: ---- FORCE UTF-8 ENCODING FOR PYTHON ----
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: ---- VALIDATION ----
if not exist "%PROJECT_DIR%\manage.py" (
    echo manage.py not found in PROJECT_DIR
    pause
    exit /b
)

if not exist "%PYTHON%" (
    echo Python not found at:
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
    echo DB dump failed!
) else (
    echo DB dump completed successfully
)

pause