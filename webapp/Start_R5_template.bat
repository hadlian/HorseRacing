@echo off
title R5 Analyzer

cd /d "__PROJECT_DIR__\webapp"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found.
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)

:: Kill any existing server on port 5050
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :5050 ^| findstr LISTENING') do (
    taskkill /F /PID %%a ^>nul 2^>&1
    echo Stopped previous server.
)

start http://localhost:5050

.venv\Scripts\python.exe app.py

pause
