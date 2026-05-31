@echo off
setlocal enabledelayedexpansion
title R5 Analyzer - Windows Setup

:: ─────────────────────────────────────────────────────────────────────────────
:: R5 Analyzer — Windows Setup
:: Run once to install everything. Safe to re-run at any time.
:: ─────────────────────────────────────────────────────────────────────────────

set "WEBAPP_DIR=%~dp0"
:: Strip trailing backslash
if "%WEBAPP_DIR:~-1%"=="\" set "WEBAPP_DIR=%WEBAPP_DIR:~0,-1%"
:: Project dir is one level up
for %%i in ("%WEBAPP_DIR%\..") do set "PROJECT_DIR=%%~fi"

set ERRORS=0

echo.
echo  ============================================================
echo   R5 Analyzer -- Windows Setup
echo   Project : %PROJECT_DIR%
echo   Webapp  : %WEBAPP_DIR%
echo  ============================================================

:: ── 1. Python ────────────────────────────────────────────────────────────────
echo.
echo [1] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo     ERROR: Python not found.
    echo     Install from: https://python.org/downloads
    echo     Make sure to check "Add Python to PATH" during install.
    set /a ERRORS+=1
    goto SKIP_PY_VER
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if !PYMAJ! LSS 3 (
    echo     ERROR: Python !PYVER! too old -- need 3.10 or later
    set /a ERRORS+=1
) else if !PYMAJ! EQU 3 if !PYMIN! LSS 10 (
    echo     ERROR: Python !PYVER! too old -- need 3.10 or later
    set /a ERRORS+=1
) else (
    echo     OK: Python !PYVER!
)
:SKIP_PY_VER

:: ── 2. Webapp virtual environment ─────────────────────────────────────────────
echo.
echo [2] Webapp virtual environment...
if not exist "%WEBAPP_DIR%\.venv" (
    echo     Creating webapp\.venv ...
    python -m venv "%WEBAPP_DIR%\.venv"
    if !errorlevel! neq 0 (
        echo     ERROR: Failed to create venv
        set /a ERRORS+=1
    ) else (
        echo     OK: Created
    )
) else (
    echo     OK: Already exists
)

:: ── 3. Webapp packages (Flask) ────────────────────────────────────────────────
echo.
echo [3] Installing webapp packages...
if exist "%WEBAPP_DIR%\.venv\Scripts\pip.exe" (
    "%WEBAPP_DIR%\.venv\Scripts\pip.exe" install --quiet --upgrade pip
    "%WEBAPP_DIR%\.venv\Scripts\pip.exe" install --quiet -r "%WEBAPP_DIR%\requirements.txt"
    "%WEBAPP_DIR%\.venv\Scripts\python.exe" -c "import flask; print('    OK: Flask ' + flask.__version__)"
    if !errorlevel! neq 0 (
        echo     ERROR: Flask install failed
        set /a ERRORS+=1
    )
) else (
    echo     ERROR: webapp venv not ready -- skipping
    set /a ERRORS+=1
)

:: ── 4. Engine virtual environment ─────────────────────────────────────────────
echo.
echo [4] Engine virtual environment...
if not exist "%PROJECT_DIR%\venv" (
    echo     Creating engine venv ...
    python -m venv "%PROJECT_DIR%\venv"
    if !errorlevel! neq 0 (
        echo     ERROR: Failed to create engine venv
        set /a ERRORS+=1
    ) else (
        echo     OK: Created
    )
) else (
    echo     OK: Already exists
)

:: ── 5. Engine packages ────────────────────────────────────────────────────────
echo.
echo [5] Installing engine packages (this may take a minute)...
if exist "%PROJECT_DIR%\requirements_engine.txt" (
    if exist "%PROJECT_DIR%\venv\Scripts\pip.exe" (
        "%PROJECT_DIR%\venv\Scripts\pip.exe" install --quiet --upgrade pip
        "%PROJECT_DIR%\venv\Scripts\pip.exe" install --quiet -r "%PROJECT_DIR%\requirements_engine.txt"
        :: Spot-check key packages
        set ENGINE_OK=1
        for %%p in (anthropic pdfplumber reportlab requests openpyxl) do (
            "%PROJECT_DIR%\venv\Scripts\python.exe" -c "import %%p" >nul 2>&1
            if !errorlevel! neq 0 (
                echo     WARNING: %%p not found after install
                set ENGINE_OK=0
            )
        )
        if !ENGINE_OK! equ 1 (
            echo     OK: All engine packages installed
        ) else (
            set /a ERRORS+=1
        )
    )
) else (
    echo     ERROR: requirements_engine.txt not found
    set /a ERRORS+=1
)

:: ── 6. Anthropic API key ──────────────────────────────────────────────────────
echo.
echo [6] Checking ANTHROPIC_API_KEY...
if defined ANTHROPIC_API_KEY (
    echo     OK: Found in environment
) else (
    echo     WARNING: ANTHROPIC_API_KEY is not set.
    echo     Auto Scout will not work until you add it:
    echo       1. Search "Environment Variables" in Start Menu
    echo       2. Under User Variables, click New
    echo       3. Name: ANTHROPIC_API_KEY  Value: sk-ant-...
    echo       4. Restart this setup script after saving
)

:: ── 7. Desktop shortcut ───────────────────────────────────────────────────────
echo.
echo [7] Creating desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\Start R5.bat"
(
    echo @echo off
    echo title R5 Analyzer
    echo.
    echo :: Kill any existing server on port 5050
    echo for /f "tokens=5" %%%%a in ^('netstat -aon 2^^^>nul ^| findstr :5050 ^| findstr LISTENING'^) do ^(
    echo     taskkill /F /PID %%%%a ^^^>nul 2^^^>^^^&1
    echo     echo Stopped previous server.
    echo ^)
    echo.
    echo :: Use absolute path to venv Python -- avoids activate not carrying through start /B
    echo :: Empty "" title required -- first quoted arg to start is window title, not executable
    echo start "" /B "%PROJECT_DIR%\webapp\.venv\Scripts\python.exe" "%PROJECT_DIR%\webapp\app.py"
    echo timeout /t 2 /nobreak ^^^>nul
    echo start http://localhost:5050
) > "%SHORTCUT%"
if exist "%SHORTCUT%" (
    echo     OK: Desktop\Start R5.bat created
) else (
    echo     ERROR: Could not create shortcut
    set /a ERRORS+=1
)

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo  ============================================================
if !ERRORS! equ 0 (
    echo   Setup complete!
    echo.
    echo   Double-click 'Start R5' on your Desktop to launch.
    echo   Then open http://localhost:5050 in your browser.
) else (
    echo   Setup finished with !ERRORS! error(s).
    echo   Fix the issues above and re-run this script.
)
echo  ============================================================
echo.
pause
