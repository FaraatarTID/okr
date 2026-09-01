@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0..\.."

set "COMPOSE_FILE=deploy\docker\docker-compose.yml"
set "ENV_FILE=deploy\docker\.env"
set "ENV_TEMPLATE=deploy\docker\.env.example"
set "SECRETS_FILE=deploy\secrets\secrets.toml"
set "SECRETS_TEMPLATE=deploy\secrets\secrets.toml.example"
set "DOCKER_EXE="

echo ==========================================
echo    OKR Tracker - Hybrid SPA Launcher
echo ==========================================
echo.

echo [1/6] Checking Docker CLI...
where docker >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%D in ('where docker') do (
        if not defined DOCKER_EXE set "DOCKER_EXE=%%D"
    )
) else (
    if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
        set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\resources\bin\docker.exe"
    )
    if not defined DOCKER_EXE if exist "%ProgramFiles(x86)%\Docker\Docker\resources\bin\docker.exe" (
        set "DOCKER_EXE=%ProgramFiles(x86)%\Docker\Docker\resources\bin\docker.exe"
    )
)

if not defined DOCKER_EXE (
    echo [ERROR] Docker is not found in PATH and default Docker Desktop location was not found.
    echo Install Docker Desktop ^(or Docker Engine + Compose plugin^) and retry.
    pause
    exit /b 1
)

echo [INFO] Using Docker CLI: !DOCKER_EXE!

echo [INFO] Checking Docker Compose plugin...
"!DOCKER_EXE!" compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose plugin is unavailable for this Docker CLI.
    echo Install Docker Desktop or enable Docker Compose v2 plugin, then retry.
    pause
    exit /b 1
)

echo [2/6] Checking Docker daemon...
"!DOCKER_EXE!" info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker daemon is not reachable.
    echo Start Docker Desktop and wait until it reports "Engine running", then retry.
    pause
    exit /b 1
)

echo [3/6] Validating required files...
if not exist "%COMPOSE_FILE%" (
    echo [ERROR] Missing compose file: %COMPOSE_FILE%
    pause
    exit /b 1
)

if not exist "%ENV_FILE%" (
    if exist "%ENV_TEMPLATE%" (
        echo [INFO] %ENV_FILE% is missing. Creating from template...
        copy /Y "%ENV_TEMPLATE%" "%ENV_FILE%" >nul
        echo [WARN] Review %ENV_FILE% and set real runtime values, then rerun this launcher.
    ) else (
        echo [ERROR] Missing env file and template: %ENV_FILE%
    )
    pause
    exit /b 1
)

if not exist "%SECRETS_FILE%" (
    if exist "%SECRETS_TEMPLATE%" (
        echo [INFO] %SECRETS_FILE% is missing. Creating from template...
        copy /Y "%SECRETS_TEMPLATE%" "%SECRETS_FILE%" >nul
        echo [WARN] Review %SECRETS_FILE% and set real runtime values, then rerun this launcher.
    ) else (
        echo [ERROR] Missing secrets file and template: %SECRETS_FILE%
    )
    pause
    exit /b 1
)

echo [4/6] Checking Python for runtime gate...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Python is required to run scripts/check_deploy_config.py.
    pause
    exit /b 1
)

echo [5/6] Running runtime config gate...
python scripts/check_deploy_config.py --mode runtime --env-file "%ENV_FILE%" --secrets-file "%SECRETS_FILE%"
if %errorlevel% neq 0 (
    echo [ERROR] Runtime config gate failed. Fix config values and rerun.
    pause
    exit /b 1
)

echo [6/6] Starting upgraded hybrid stack (backend-api + backend-worker + spa-bff + spa-web)...
"!DOCKER_EXE!" compose -f "%COMPOSE_FILE%" up -d --build backend-api backend-worker spa-bff spa-web
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start hybrid stack.
    pause
    exit /b 1
)

echo.
echo [OK] Hybrid stack is up.
echo - SPA Web: http://127.0.0.1:3000
echo - Backend API: http://127.0.0.1:8100
echo - SPA BFF:     http://127.0.0.1:3001
echo.
echo [INFO] Opening SPA in your browser...
start "" "http://127.0.0.1:3000"
echo.
echo [INFO] Service status:
"!DOCKER_EXE!" compose -f "%COMPOSE_FILE%" ps
echo.
pause
exit /b 0
