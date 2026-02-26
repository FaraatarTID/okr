@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "ROOT=%~dp0"
set "ROOT_CLEAN=%ROOT%"
if "%ROOT_CLEAN:~-1%"=="\" set "ROOT_CLEAN=%ROOT_CLEAN:~0,-1%"
set "DOCKER_ENV_FILE=deploy\docker\.env"
set "SECRETS_FILE=deploy\secrets\secrets.toml"
set "VENV_DIR=.venv"
set "PYEXE=%ROOT%%VENV_DIR%\Scripts\python.exe"
set "POWERSHELL_EXE=powershell"
set "LOG_DIR=%ROOT%tmp\local-hybrid-logs"
set "BACKEND_OUT_LOG=%LOG_DIR%\backend-api.out.log"
set "BACKEND_ERR_LOG=%LOG_DIR%\backend-api.err.log"
set "WORKER_OUT_LOG=%LOG_DIR%\backend-worker.out.log"
set "WORKER_ERR_LOG=%LOG_DIR%\backend-worker.err.log"
set "BFF_OUT_LOG=%LOG_DIR%\spa-bff.out.log"
set "BFF_ERR_LOG=%LOG_DIR%\spa-bff.err.log"
set "SPA_OUT_LOG=%LOG_DIR%\spa-web.out.log"
set "SPA_ERR_LOG=%LOG_DIR%\spa-web.err.log"

echo ==========================================
echo  OKR Tracker - Hybrid Local Launcher
echo ==========================================
echo.

echo [1/7] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH.
    pause
    exit /b 1
)

echo [2/7] Checking Node.js + npm...
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not found in PATH.
    pause
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is not found in PATH.
    pause
    exit /b 1
)
where "%POWERSHELL_EXE%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell is not found in PATH.
    pause
    exit /b 1
)

for /f %%V in ('node -p "process.versions.node.split('.')[0]"') do set "NODE_MAJOR=%%V"
if not defined NODE_MAJOR (
    echo [ERROR] Failed to detect Node.js major version.
    pause
    exit /b 1
)
if %NODE_MAJOR% lss 20 (
    echo [ERROR] Node.js v20+ is required. Detected major version: %NODE_MAJOR%
    pause
    exit /b 1
)

echo [3/7] Resolving database URL...
set "DB_URL_CANDIDATE=%OKR_DATABASE_URL%"
set "OKR_DATABASE_URL="

if defined DB_URL_CANDIDATE call :accept_db_url_if_valid "%DB_URL_CANDIDATE%" "env:OKR_DATABASE_URL"
if not defined OKR_DATABASE_URL if defined DATABASE_URL call :accept_db_url_if_valid "%DATABASE_URL%" "env:DATABASE_URL"

set "DB_URL_CANDIDATE="
if not defined OKR_DATABASE_URL if exist "%DOCKER_ENV_FILE%" for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%DOCKER_ENV_FILE%") do if not defined DB_URL_CANDIDATE if not "%%B"=="" if /I "%%A"=="OKR_DATABASE_URL" set "DB_URL_CANDIDATE=%%~B"
if not defined OKR_DATABASE_URL if exist "%DOCKER_ENV_FILE%" for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%DOCKER_ENV_FILE%") do if not defined DB_URL_CANDIDATE if not "%%B"=="" if /I "%%A"=="DATABASE_URL" set "DB_URL_CANDIDATE=%%~B"
if not defined OKR_DATABASE_URL if defined DB_URL_CANDIDATE call :accept_db_url_if_valid "%DB_URL_CANDIDATE%" "%DOCKER_ENV_FILE%"

set "DB_URL_CANDIDATE="
if not defined OKR_DATABASE_URL if exist "%SECRETS_FILE%" set "OKR_SECRETS_FILE=%SECRETS_FILE%"
if not defined OKR_DATABASE_URL if exist "%SECRETS_FILE%" for /f "usebackq delims=" %%U in (`python -c "import os,pathlib,tomllib; p=pathlib.Path(os.environ.get('OKR_SECRETS_FILE','')); d=tomllib.load(p.open('rb')) if p.exists() else {}; db=d.get('OKR_DATABASE_URL') or d.get('DATABASE_URL') or ((d.get('database') or {}).get('url')) or ''; print(str(db).strip())" 2^>nul`) do set "DB_URL_CANDIDATE=%%U"
if not defined OKR_DATABASE_URL if defined DB_URL_CANDIDATE call :accept_db_url_if_valid "%DB_URL_CANDIDATE%" "%SECRETS_FILE%"

if not defined OKR_DATABASE_URL (
    echo [ERROR] Could not resolve a valid OKR_DATABASE_URL.
    echo Checked env vars, %DOCKER_ENV_FILE%, and %SECRETS_FILE%.
    pause
    exit /b 1
)
set "DATABASE_URL=%OKR_DATABASE_URL%"

echo [4/7] Preparing Python environment...
if not exist "%PYEXE%" (
    echo [INFO] Creating virtual environment in %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

"%PYEXE%" -c "import fastapi,uvicorn,sqlmodel,psycopg2" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Python dependencies...
    "%PYEXE%" -m pip install -r "backend_app\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
)

echo [5/7] Preparing Node dependencies...
if not exist "%ROOT%spa-bff\package.json" (
    echo [ERROR] Missing spa-bff\package.json.
    pause
    exit /b 1
)
if not exist "%ROOT%spa-web\package.json" (
    echo [ERROR] Missing spa-web\package.json.
    pause
    exit /b 1
)

if not exist "%ROOT%spa-bff\node_modules" (
    echo [INFO] Installing spa-bff dependencies...
    call npm --prefix "%ROOT%spa-bff" install
    if errorlevel 1 (
        echo [ERROR] Failed to install spa-bff dependencies.
        pause
        exit /b 1
    )
)
if not exist "%ROOT%spa-web\node_modules" (
    echo [INFO] Installing spa-web dependencies...
    call npm --prefix "%ROOT%spa-web" install
    if errorlevel 1 (
        echo [ERROR] Failed to install spa-web dependencies.
        pause
        exit /b 1
    )
)
echo [INFO] Clearing stale Next.js cache...
if exist "%ROOT%spa-web\.next" rd /s /q "%ROOT%spa-web\.next" >nul 2>&1
echo [INFO] Building spa-web production bundle...
call npm --prefix "%ROOT%spa-web" run build
if errorlevel 1 (
    echo [ERROR] Failed to build spa-web.
    pause
    exit /b 1
)

echo [6/7] Setting runtime environment...
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
set "OKR_ENV=development"
set "OKR_BACKEND_HOST=127.0.0.1"
set "OKR_BACKEND_PORT=8100"
set "OKR_BACKEND_ENFORCE_TOKEN=true"
set "OKR_BACKEND_SERVICE_TOKEN=local-development-secret-token"
set "OKR_BACKEND_ENFORCE_REQUEST_SIGNING=false"
set "OKR_BACKEND_SIGNING_SECRET="
set "OKR_BACKEND_SECURITY_STATE_BACKEND=memory"
set "OKR_BACKEND_API_URL=http://127.0.0.1:8100"
set "BFF_HOST=127.0.0.1"
set "BFF_PORT=3001"
set "BFF_PUBLIC_ORIGIN=http://127.0.0.1:3001"
set "BFF_REQUEST_TIMEOUT_MS=90000"
set "OKR_SPA_ROLLOUT_ENABLED=true"
set "OKR_SPA_ROLLOUT_ALLOW_ALL=true"

echo [7/9] Launching backend + worker + BFF + SPA...
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if exist "%BACKEND_OUT_LOG%" del /q "%BACKEND_OUT_LOG%" >nul 2>&1
if exist "%BACKEND_ERR_LOG%" del /q "%BACKEND_ERR_LOG%" >nul 2>&1
if exist "%WORKER_OUT_LOG%" del /q "%WORKER_OUT_LOG%" >nul 2>&1
if exist "%WORKER_ERR_LOG%" del /q "%WORKER_ERR_LOG%" >nul 2>&1
if exist "%BFF_OUT_LOG%" del /q "%BFF_OUT_LOG%" >nul 2>&1
if exist "%BFF_ERR_LOG%" del /q "%BFF_ERR_LOG%" >nul 2>&1
if exist "%SPA_OUT_LOG%" del /q "%SPA_OUT_LOG%" >nul 2>&1
if exist "%SPA_ERR_LOG%" del /q "%SPA_ERR_LOG%" >nul 2>&1

echo [INFO] Stopping stale local hybrid processes (if any)...
call :stop_stale_hybrid_processes

echo [INFO] Launching Backend API process...
set "SPAWN_CWD=%ROOT_CLEAN%"
set "SPAWN_EXE=%PYEXE%"
set "SPAWN_ARGS=-m backend_app.run_api"
set "SPAWN_OUT=%BACKEND_OUT_LOG%"
set "SPAWN_ERR=%BACKEND_ERR_LOG%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_backend_failed

echo [INFO] Launching Backend Worker process...
set "SPAWN_CWD=%ROOT_CLEAN%"
set "SPAWN_EXE=%PYEXE%"
set "SPAWN_ARGS=-m backend_app.worker"
set "SPAWN_OUT=%WORKER_OUT_LOG%"
set "SPAWN_ERR=%WORKER_ERR_LOG%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_worker_failed

echo [INFO] Launching SPA BFF process...
set "SPAWN_CWD=%ROOT_CLEAN%\spa-bff"
set "SPAWN_EXE=cmd.exe"
set "SPAWN_ARGS=/d /c npm run dev"
set "SPAWN_OUT=%BFF_OUT_LOG%"
set "SPAWN_ERR=%BFF_ERR_LOG%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_bff_failed

echo [INFO] Launching SPA Web process...
set "SPAWN_CWD=%ROOT_CLEAN%\spa-web"
set "SPAWN_EXE=cmd.exe"
set "SPAWN_ARGS=/d /c npm run start -- -p 3000 -H 127.0.0.1"
set "SPAWN_OUT=%SPA_OUT_LOG%"
set "SPAWN_ERR=%SPA_ERR_LOG%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_spa_failed

echo [8/9] Waiting for service readiness...
call :wait_for_http "Backend API" "http://127.0.0.1:8100/healthz" 60
if errorlevel 1 goto :startup_failed
call :wait_for_worker "Backend Worker" "backend_app.worker" 60
if errorlevel 1 goto :startup_failed
call :wait_for_http "SPA BFF" "http://127.0.0.1:3001/healthz" 60
if errorlevel 1 goto :startup_failed
call :wait_for_http "SPA Web" "http://127.0.0.1:3000" 120
if errorlevel 1 goto :startup_failed

echo [9/9] Checking async job pipeline readiness...
call :wait_for_worker "Backend Worker" "backend_app.worker" 20
if errorlevel 1 goto :startup_failed

echo.
echo [OK] Local hybrid services launched.
echo - Backend API: http://127.0.0.1:8100
echo - Backend Worker: active
echo - SPA BFF:     http://127.0.0.1:3001
echo - SPA Web:     http://127.0.0.1:3000
echo - Logs:        %LOG_DIR%
echo.
echo [INFO] Opening SPA Web...
start "" "http://127.0.0.1:3000"
echo.
pause
exit /b 0

:spawn_backend_failed
echo [ERROR] Failed to launch Backend API process.
goto :startup_failed

:spawn_worker_failed
echo [ERROR] Failed to launch Backend Worker process.
goto :startup_failed

:spawn_bff_failed
echo [ERROR] Failed to launch SPA BFF process.
goto :startup_failed

:spawn_spa_failed
echo [ERROR] Failed to launch SPA Web process.
goto :startup_failed

:accept_db_url_if_valid
set "DB_URL_CANDIDATE=%~1"
set "DB_URL_SOURCE=%~2"
if "%DB_URL_CANDIDATE%"=="" exit /b 1
set "OKR_DB_URL_CANDIDATE=%DB_URL_CANDIDATE%"
set "DB_URL_CHECK="
for /f "usebackq delims=" %%R in (`python -c "import os; from urllib.parse import urlparse; u=str(os.environ.get('OKR_DB_URL_CANDIDATE','')).strip(); up=u.upper(); host=(urlparse(u).hostname or '').lower() if u else ''; print('placeholder' if any(t in up for t in ('PROJECT_REF','DB_PASSWORD','AWS-0-REGION','CHANGE_ME')) else ('docker_internal' if host in ('db','postgres','backend-api') else ('empty' if not u else 'ok')))"`) do set "DB_URL_CHECK=%%R"
if /I "%DB_URL_CHECK%"=="ok" (
    set "OKR_DATABASE_URL=%DB_URL_CANDIDATE%"
    echo [INFO] Using OKR_DATABASE_URL from %DB_URL_SOURCE%.
    exit /b 0
)
if /I "%DB_URL_CHECK%"=="placeholder" (
    echo [WARN] Ignoring DB URL from %DB_URL_SOURCE% because it contains template values.
    exit /b 1
)
if /I "%DB_URL_CHECK%"=="docker_internal" (
    echo [WARN] Ignoring DB URL from %DB_URL_SOURCE% because it uses Docker-internal host.
    exit /b 1
)
echo [WARN] Ignoring DB URL from %DB_URL_SOURCE%.
exit /b 1

:wait_for_http
set "SERVICE_NAME=%~1"
set "SERVICE_URL=%~2"
set "MAX_RETRIES=%~3"
set /a RETRY_COUNT=0
:wait_for_http_loop
set /a RETRY_COUNT=RETRY_COUNT+1
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%SERVICE_URL%' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } ; exit 1 } catch { exit 1 }"
if not errorlevel 1 (
    echo [OK] %SERVICE_NAME% is reachable.
    exit /b 0
)
if %RETRY_COUNT% geq %MAX_RETRIES% (
    echo [ERROR] %SERVICE_NAME% is not reachable at %SERVICE_URL%.
    exit /b 1
)
timeout /t 1 /nobreak >nul
if %RETRY_COUNT% equ 1 echo [INFO] Waiting for %SERVICE_NAME%...
set /a WAIT_PROGRESS_REMAINDER=RETRY_COUNT%%10
if %WAIT_PROGRESS_REMAINDER% equ 0 echo [INFO] Still waiting for %SERVICE_NAME%... (%RETRY_COUNT%s)
goto :wait_for_http_loop

:wait_for_worker
set "SERVICE_NAME=%~1"
set "WORKER_PATTERN=%~2"
set "MAX_RETRIES=%~3"
set /a RETRY_COUNT=0
:wait_for_worker_loop
set /a RETRY_COUNT=RETRY_COUNT+1
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "$cmds = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*%WORKER_PATTERN%*' }; if ($cmds) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
    echo [OK] %SERVICE_NAME% is running.
    exit /b 0
)
if %RETRY_COUNT% geq %MAX_RETRIES% (
    echo [ERROR] %SERVICE_NAME% process was not detected.
    exit /b 1
)
timeout /t 1 /nobreak >nul
if %RETRY_COUNT% equ 1 echo [INFO] Waiting for %SERVICE_NAME%...
set /a WAIT_PROGRESS_REMAINDER=RETRY_COUNT%%10
if %WAIT_PROGRESS_REMAINDER% equ 0 echo [INFO] Still waiting for %SERVICE_NAME%... (%RETRY_COUNT%s)
goto :wait_for_worker_loop

:startup_failed
echo.
echo [ERROR] Local hybrid startup failed. Showing last log lines:
call :print_log_tail "Backend API stdout" "%BACKEND_OUT_LOG%"
call :print_log_tail "Backend API stderr" "%BACKEND_ERR_LOG%"
call :print_log_tail "Backend Worker stdout" "%WORKER_OUT_LOG%"
call :print_log_tail "Backend Worker stderr" "%WORKER_ERR_LOG%"
call :print_log_tail "SPA BFF stdout" "%BFF_OUT_LOG%"
call :print_log_tail "SPA BFF stderr" "%BFF_ERR_LOG%"
call :print_log_tail "SPA Web stdout" "%SPA_OUT_LOG%"
call :print_log_tail "SPA Web stderr" "%SPA_ERR_LOG%"
echo.
echo [INFO] Full logs are in: %LOG_DIR%
pause
exit /b 1

:print_log_tail
set "LOG_LABEL=%~1"
set "LOG_PATH=%~2"
echo ----- %LOG_LABEL% -----
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "if (Test-Path '%LOG_PATH%') { Get-Content -Path '%LOG_PATH%' -Tail 60 } else { Write-Host '[log file not found]' }"
echo.
exit /b 0

:spawn_with_logs
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "$cwd=[Environment]::GetEnvironmentVariable('SPAWN_CWD');" ^
    "$exe=[Environment]::GetEnvironmentVariable('SPAWN_EXE');" ^
    "$args=[Environment]::GetEnvironmentVariable('SPAWN_ARGS');" ^
    "$out=[Environment]::GetEnvironmentVariable('SPAWN_OUT');" ^
    "$err=[Environment]::GetEnvironmentVariable('SPAWN_ERR');" ^
    "try { Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $cwd -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -ErrorAction Stop | Out-Null; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
exit /b %ERRORLEVEL%

:stop_stale_hybrid_processes
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "$root = [Environment]::GetEnvironmentVariable('ROOT_CLEAN');" ^
    "$regex = 'backend_app.run_api|backend_app.worker|spa-bff|spa-web\\\\node_modules\\\\.*next\\\\dist\\\\bin\\\\next|next start -- -p 3000|tsx watch';" ^
    "$currentPid = $PID;" ^
    "$byCommand = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $cmd = [string]$_.CommandLine; $name = [string]$_.Name; $_.ProcessId -ne $currentPid -and $cmd -and $cmd.Contains($root) -and ($name -in @('python.exe','node.exe','cmd.exe')) -and ($cmd -match $regex) } | Select-Object -ExpandProperty ProcessId;" ^
    "$byPort = @(); foreach ($port in @(8100, 3001, 3000)) { try { $byPort += (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess) } catch {} };" ^
    "$targets = @($byCommand + $byPort) | Where-Object { $_ } | Sort-Object -Unique;" ^
    "foreach ($procId in $targets) { try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } catch {} }"
exit /b 0
