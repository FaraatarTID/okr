@echo off
setlocal enabledelayedexpansion

REM Change directory to the script's location
cd /d "%~dp0"

echo ==========================================
echo      OKR Tracker - Streamlit Launcher
echo ==========================================
echo.

echo [1/3] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in your PATH.
    echo Please install Python 3.10 or higher from python.org and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)
python --version
echo.

echo [2/3] Checking dependencies...
REM Attempt to import critical packages to verify environment
REM If imports fail, we assume dependencies are missing.
python -c "import streamlit, google.genai, dotenv, gspread, google.auth, streamlit_agraph, pdfkit" >nul 2>&1

if %errorlevel% neq 0 (
    echo [INFO] Missing or incomplete dependencies detected.
    echo [INFO] Installing required packages...
    echo.
    pip install -r streamlit_app/requirements.txt
    
    if !errorlevel! neq 0 (
        echo.
        echo [ERROR] Failed to install dependencies.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
    echo.
    echo [SUCCESS] Dependencies installed!
) else (
    echo [INFO] All dependencies are already installed.
)
echo.

echo [3/3] Launching Application...
echo.
REM Navigate to app directory so data files are found locally
cd streamlit_app
streamlit run app.py

if %errorlevel% neq 0 (
    echo.
    echo [WARN] App closed with an error or Ctrl+C.
    pause
)
