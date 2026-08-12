@echo off
REM ================================
REM VGSync Local Server Starter
REM ================================

echo Starting VGSync local server...

REM Allow PowerShell scripts temporarily
powershell -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass"

REM Navigate to your project directory
cd /d "D:\vgsync\vgsync-backend"

REM Activate virtual environment
call venv\Scripts\activate

REM Run Django server on all network interfaces (so mobile can access via IP)
python manage.py runserver 0.0.0.0:8000

pause