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
REM Use a virtual environment and verify each required package individually.
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

echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo [INFO] Upgrading pip and essential build tools...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1

echo [INFO] Installing packages from requirements.txt...
pip install --quiet -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies from requirements.txt.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

echo [INFO] Verifying installed packages by attempting imports...
echo import sys, importlib > temp_verify.py
echo names = ['streamlit', 'sqlmodel', 'pydantic', 'google.generativeai', 'plotly', 'dotenv', 'gspread', 'google.auth', 'streamlit_agraph', 'google.genai', 'pdfkit', 'requests'] >> temp_verify.py
echo missing = [] >> temp_verify.py
echo for n in names: >> temp_verify.py
echo     try: >> temp_verify.py
echo         importlib.import_module(n) >> temp_verify.py
echo     except Exception as e: >> temp_verify.py
echo         missing.append(n) >> temp_verify.py
echo if missing: >> temp_verify.py
echo     print('[ERROR] Missing modules: ' + ', '.join(missing)) >> temp_verify.py
echo     sys.exit(1) >> temp_verify.py
echo else: >> temp_verify.py
echo     print('[SUCCESS] All required modules import correctly') >> temp_verify.py
python temp_verify.py || (
    echo.
    echo [ERROR] Some packages failed to import after installation.
    echo Please inspect the error above and install missing packages manually.
    del temp_verify.py
    pause
    exit /b 1
)
del temp_verify.py
echo.

echo [3/3] Launching Application...
echo.
set LOGFILE=%~dp0run_app.log
echo [INFO] Starting Streamlit in background (logs -> %LOGFILE%)...
echo.

REM Start Streamlit in background with headless mode to prevent auto-open
start /b python -m streamlit run app.py --server.headless=true > "%LOGFILE%" 2>&1

REM Wait a moment for it to start
timeout /t 3 /nobreak >nul

REM Open in a new browser window
start "" rundll32 url.dll,FileProtocolHandler "http://localhost:8501"

echo [INFO] App launched in new browser window. Closing launcher.
echo Full log saved at: %LOGFILE%
exit /b 0
