@echo off
setlocal

REM Change directory to the script's location
cd /d "%~dp0"

echo ==========================================
echo      OKR Tracker - Streamlit Launcher
echo ==========================================
echo.

echo [1/2] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in your PATH.
    echo Please install Python 3.10 or higher from python.org and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)
python --version
echo.

echo [2/2] Preparing virtual environment...
REM Use a virtual environment and install dependencies if needed.
set VENV_DIR=venv

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment in %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set PYEXE=%VENV_DIR%\Scripts\python.exe
if not exist "%PYEXE%" (
    echo [ERROR] Virtual environment python not found at %PYEXE%.
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
set DEP_FLAG=%~dp0.deps_installed
if not exist "%DEP_FLAG%" (
    echo [INFO] Installing dependencies from requirements.txt...
    %PYEXE% -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies from requirements.txt.
        pause
        exit /b 1
    )
    echo done > "%DEP_FLAG%"
) else (
    echo [INFO] Dependencies already installed.
)

echo.
echo [INFO] Starting Streamlit...
echo.
start "" /b "%PYEXE%" -m streamlit run app.py --server.headless=true

REM Wait a moment for the server to start, then open the app
timeout /t 3 /nobreak >nul
start "" "http://localhost:8501/"

echo [INFO] Streamlit is running in the background. Close this window to stop showing messages.
pause
exit /b 0
