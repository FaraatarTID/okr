@echo off
setlocal EnableExtensions EnableDelayedExpansion

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
set "REQ_FILE=requirements.txt"
set "DEP_HASH_FILE=%~dp0.deps_hash"
set "NEED_INSTALL=0"
set "CURR_HASH="
set "STORED_HASH="

if not exist "%REQ_FILE%" (
    echo [ERROR] requirements.txt not found.
    pause
    exit /b 1
)

for /f "tokens=* delims=" %%H in ('certutil -hashfile "%REQ_FILE%" SHA256 ^| findstr /R /I "^[0-9A-F ][0-9A-F ]*$"') do (
    set "CURR_HASH=%%H"
)
set "CURR_HASH=!CURR_HASH: =!"

if not defined CURR_HASH (
    echo [WARN] Could not compute requirements hash. Installing dependencies.
    set "NEED_INSTALL=1"
) else (
    if exist "%DEP_HASH_FILE%" (
        set /p STORED_HASH=<"%DEP_HASH_FILE%"
    )

    if /I "!CURR_HASH!"=="!STORED_HASH!" (
        echo [INFO] requirements.txt unchanged. Verifying core packages...
        %PYEXE% -c "import streamlit,sqlmodel,alembic,psycopg2" >nul 2>&1
        if errorlevel 1 (
            echo [INFO] Core dependency check failed. Reinstalling requirements...
            set "NEED_INSTALL=1"
        ) else (
            echo [INFO] Dependencies are up to date.
        )
    ) else (
        echo [INFO] requirements.txt changed. Installing/updating dependencies...
        set "NEED_INSTALL=1"
    )
)

if "!NEED_INSTALL!"=="1" (
    %PYEXE% -m pip install -r "%REQ_FILE%"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies from requirements.txt.
        pause
        exit /b 1
    )
    if defined CURR_HASH (
        > "%DEP_HASH_FILE%" echo !CURR_HASH!
    )
)

echo.
echo [INFO] Starting Streamlit...
echo.
start "" /b "%PYEXE%" -m streamlit run login_app.py --server.headless=true

REM Wait a moment for the server to start, then open the app
timeout /t 3 /nobreak >nul
start "" "http://localhost:8501/"

echo [INFO] Streamlit is running in the background. Close this window to stop showing messages.
pause
exit /b 0
