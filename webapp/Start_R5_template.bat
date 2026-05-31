@echo off
title R5 Analyzer

:: Kill any existing server on port 5050
for /f "tokens=5" %%a in ('netstat -aon 2^>nul | findstr :5050 | findstr LISTENING') do (
    taskkill /F /PID %%a ^>nul 2^>^&1
    echo Stopped previous server.
)

start "" /B "__PROJECT_DIR__\webapp\.venv\Scripts\python.exe" "__PROJECT_DIR__\webapp\app.py"
timeout /t 2 /nobreak >nul
start http://localhost:5050
