@echo off
REM ================================
REM VGSync Local Server Starter
REM ================================

echo Starting VGSync local server...

REM Allow PowerShell scripts temporarily
powershell -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass"

REM Navigate to your project directory (edit path below)
cd /d "D:\Projects\django\vgsync-backend"

REM Activate virtual environment (edit 'venv' if your folder name differs)
call env\Scripts\activate

REM Run Django server on all network interfaces (so mobile can access via IP)
python manage.py runserver 0.0.0.0:8000

pause
