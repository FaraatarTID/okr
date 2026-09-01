@echo off
setlocal EnableExtensions

cd /d "%~dp0..\.."
set "ROOT=%~dp0..\..\"
set "ROOT_CLEAN=%ROOT%"
if "%ROOT_CLEAN:~-1%"=="\" set "ROOT_CLEAN=%ROOT_CLEAN:~0,-1%"
set "DOCKER_ENV_FILE=deploy\docker\.env"
set "SECRETS_FILE=deploy\secrets\secrets.toml"
set "VENV_DIR=.venv"
set "PYEXE=%ROOT%%VENV_DIR%\Scripts\python.exe"
set "POWERSHELL_EXE=powershell"
set "LOG_DIR=%ROOT%tmp\local-hybrid-logs"
set "LOCAL_SQLITE_PATH=%ROOT%tmp\okr-local-dev.sqlite3"
set "BACKEND_OUT_LOG=%LOG_DIR%\backend-api.out.log"
set "BACKEND_ERR_LOG=%LOG_DIR%\backend-api.err.log"
set "WORKER_OUT_LOG=%LOG_DIR%\backend-worker.out.log"
set "WORKER_ERR_LOG=%LOG_DIR%\backend-worker.err.log"
set "BFF_OUT_LOG=%LOG_DIR%\spa-bff.out.log"
set "BFF_ERR_LOG=%LOG_DIR%\spa-bff.err.log"
set "SPA_OUT_LOG=%LOG_DIR%\spa-web.out.log"
set "SPA_ERR_LOG=%LOG_DIR%\spa-web.err.log"
set "PID_FILE=%LOG_DIR%\local-hybrid.pids"
set "LAST_PID_FILE=%LOG_DIR%\last-spawn.pid"
set "BACKEND_PID="

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
call :ensure_local_db_reachable
if errorlevel 1 (
    pause
    exit /b 1
)
set "DATABASE_URL=%OKR_DATABASE_URL%"
call :fallback_to_local_sqlite_if_remote_unreachable
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
set "OKR_ALLOW_NON_SUPABASE_DB=true"
set "OKR_BACKEND_HOST=127.0.0.1"
set "OKR_BACKEND_PORT=8100"
set "OKR_BACKEND_API_URL=http://127.0.0.1:8100"
set "OKR_BACKEND_ENFORCE_TOKEN=true"
set "OKR_BACKEND_SERVICE_TOKEN=local-development-secret-token"
set "OKR_BACKEND_ENFORCE_REQUEST_SIGNING=false"
set "OKR_BACKEND_SIGNING_SECRET="
set "OKR_BACKEND_SECURITY_STATE_BACKEND=memory"
set "OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS=60"
set "OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS=5000"
set "OKR_BACKEND_API_URL=http://127.0.0.1:8100"
set "BFF_HOST=127.0.0.1"
set "BFF_PORT=3001"
set "BFF_PUBLIC_ORIGIN=http://127.0.0.1:3001"
set "BFF_REQUEST_TIMEOUT_MS=20000"
set "BFF_SESSION_SECRET=local-dev-session-secret"
set "BFF_SESSION_TTL_SECONDS=28800"
set "BFF_COOKIE_SECURE=false"
set "OKR_SPA_ROLLOUT_ENABLED=true"
set "OKR_SPA_ROLLOUT_ALLOW_ALL=true"

echo [7/9] Launching backend + worker + BFF + SPA...
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if exist "%PID_FILE%" del /q "%PID_FILE%" >nul 2>&1
if exist "%BACKEND_OUT_LOG%" del /q "%BACKEND_OUT_LOG%" >nul 2>&1
if exist "%BACKEND_ERR_LOG%" del /q "%BACKEND_ERR_LOG%" >nul 2>&1
if exist "%WORKER_OUT_LOG%" del /q "%WORKER_OUT_LOG%" >nul 2>&1
if exist "%WORKER_ERR_LOG%" del /q "%WORKER_ERR_LOG%" >nul 2>&1
if exist "%BFF_OUT_LOG%" del /q "%BFF_OUT_LOG%" >nul 2>&1
if exist "%BFF_ERR_LOG%" del /q "%BFF_ERR_LOG%" >nul 2>&1
if exist "%SPA_OUT_LOG%" del /q "%SPA_OUT_LOG%" >nul 2>&1
if exist "%SPA_ERR_LOG%" del /q "%SPA_ERR_LOG%" >nul 2>&1
if exist "%PID_FILE%" del /q "%PID_FILE%" >nul 2>&1
if exist "%LAST_PID_FILE%" del /q "%LAST_PID_FILE%" >nul 2>&1

echo [INFO] Stopping stale local hybrid processes (if any)...
call :stop_stale_hybrid_processes

echo [INFO] Launching Backend API process...
set "SPAWN_CWD=%ROOT_CLEAN%"
set "SPAWN_EXE=%PYEXE%"
set "SPAWN_ARGS=-m backend_app.run_api"
set "SPAWN_OUT=%BACKEND_OUT_LOG%"
set "SPAWN_ERR=%BACKEND_ERR_LOG%"
set "SPAWN_PID_FILE=%PID_FILE%"
set "SPAWN_LAST_PID_FILE=%LAST_PID_FILE%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_backend_failed
call :set_last_spawned_pid_from_file
if not errorlevel 1 set "BACKEND_PID=%LAST_SPAWNED_PID%"

echo [INFO] Waiting for Backend API warm-up before launching other services...
call :wait_for_http "Backend API" "http://127.0.0.1:8100/healthz" 120
if errorlevel 1 goto :startup_failed

echo [8/9] Waiting for service readiness...
call :wait_for_http "Backend API" "http://127.0.0.1:8100/healthz" 90
if errorlevel 1 goto :startup_failed

echo [INFO] Launching Backend Worker process...
set "SPAWN_CWD=%ROOT_CLEAN%"
set "SPAWN_EXE=%PYEXE%"
set "SPAWN_ARGS=-m backend_app.worker"
set "SPAWN_OUT=%WORKER_OUT_LOG%"
set "SPAWN_ERR=%WORKER_ERR_LOG%"
set "SPAWN_PID_FILE=%PID_FILE%"
set "SPAWN_LAST_PID_FILE=%LAST_PID_FILE%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_worker_failed
call :wait_for_worker "Backend Worker" "backend_app.worker" 60
if errorlevel 1 goto :startup_failed

echo [INFO] Launching SPA BFF process...
set "SPAWN_CWD=%ROOT_CLEAN%\spa-bff"
set "SPAWN_EXE=cmd.exe"
set "SPAWN_ARGS=/d /c npm run dev"
set "SPAWN_OUT=%BFF_OUT_LOG%"
set "SPAWN_ERR=%BFF_ERR_LOG%"
set "SPAWN_PID_FILE=%PID_FILE%"
set "SPAWN_LAST_PID_FILE=%LAST_PID_FILE%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_bff_failed
call :wait_for_http "SPA BFF" "http://127.0.0.1:3001/healthz" 60
if errorlevel 1 goto :startup_failed

echo [INFO] Launching SPA Web process...
set "SPAWN_CWD=%ROOT_CLEAN%\spa-web"
set "SPAWN_EXE=cmd.exe"
set "SPAWN_ARGS=/d /c npm run start -- -p 3000 -H 127.0.0.1"
set "SPAWN_OUT=%SPA_OUT_LOG%"
set "SPAWN_ERR=%SPA_ERR_LOG%"
set "SPAWN_PID_FILE=%PID_FILE%"
set "SPAWN_LAST_PID_FILE=%LAST_PID_FILE%"
call :spawn_with_logs
if errorlevel 1 goto :spawn_spa_failed

echo [8/9] Waiting for service readiness...
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
echo - PID file:    %PID_FILE%
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

:ensure_local_db_reachable
set "DB_CONNECTIVITY_CHECK="
for /f "usebackq delims=" %%R in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$u=[string]$env:OKR_DATABASE_URL; if([string]::IsNullOrWhiteSpace($u)){ 'invalid'; exit 0 }; try { $uri=[uri]$u } catch { 'invalid'; exit 0 }; $scheme=([string]$uri.Scheme).ToLowerInvariant(); if($scheme -eq 'sqlite'){ 'ok'; exit 0 }; $dbHost=[string]$uri.Host; if([string]::IsNullOrWhiteSpace($dbHost)){ 'invalid'; exit 0 }; $port = if(($uri.IsDefaultPort) -or ($uri.Port -le 0)) { 5432 } else { [int]$uri.Port }; try { $addresses=[System.Net.Dns]::GetHostAddresses($dbHost) } catch { 'dns_fail'; exit 0 }; if(-not $addresses){ 'dns_fail'; exit 0 }; $connected=$false; foreach($addr in $addresses){ $client=$null; $waitHandle=$null; try { $client=New-Object System.Net.Sockets.TcpClient; $async=$client.BeginConnect($addr,$port,$null,$null); $waitHandle=$async.AsyncWaitHandle; if($waitHandle.WaitOne(2000)){ $client.EndConnect($async) | Out-Null; $connected=$true; break } } catch {} finally { if($waitHandle){ $waitHandle.Close() }; if($client){ $client.Close() } } }; if($connected){ 'ok' } else { 'tcp_fail' }"`) do set "DB_CONNECTIVITY_CHECK=%%R"
if /I "%DB_CONNECTIVITY_CHECK%"=="ok" (
    exit /b 0
)
set "DB_CONNECTIVITY_REASON="
if /I "%DB_CONNECTIVITY_CHECK%"=="dns_fail" set "DB_CONNECTIVITY_REASON=Remote database host is not resolvable."
if /I "%DB_CONNECTIVITY_CHECK%"=="tcp_fail" set "DB_CONNECTIVITY_REASON=Remote database host is not reachable on its TCP port."
if defined DB_CONNECTIVITY_REASON (
    set "ALLOW_SQLITE_FALLBACK=%OKR_LOCAL_DB_FALLBACK%"
    if not defined ALLOW_SQLITE_FALLBACK set "ALLOW_SQLITE_FALLBACK=true"
    if /I "%ALLOW_SQLITE_FALLBACK%"=="false" (
        echo [ERROR] %DB_CONNECTIVITY_REASON% Fallback is disabled.
        echo Set OKR_LOCAL_DB_FALLBACK=true to auto-fallback to local SQLite.
        exit /b 1
    )
    set "ALLOW_SQLITE_RESET=%OKR_LOCAL_DB_RESET%"
    if not defined ALLOW_SQLITE_RESET set "ALLOW_SQLITE_RESET=false"
    if /I "%ALLOW_SQLITE_RESET%"=="true" (
        if exist "%LOCAL_SQLITE_PATH%" (
            echo [INFO] Resetting stale local SQLite database: %LOCAL_SQLITE_PATH%
            del /q "%LOCAL_SQLITE_PATH%" >nul 2>&1
        )
    ) else (
        if exist "%LOCAL_SQLITE_PATH%" (
            echo [INFO] Reusing local SQLite database: %LOCAL_SQLITE_PATH%
        )
    )
    for /f "usebackq delims=" %%U in (`python -c "import os,pathlib; p=pathlib.Path(os.environ.get('LOCAL_SQLITE_PATH','')).resolve(); p.parent.mkdir(parents=True, exist_ok=True); print(f'sqlite:///{p.as_posix()}')"`) do set "OKR_DATABASE_URL=%%U"
    call set "DATABASE_URL=%%OKR_DATABASE_URL%%"
    echo [WARN] %DB_CONNECTIVITY_REASON% Falling back to local SQLite:
    call echo        %%OKR_DATABASE_URL%%
    exit /b 0
)
echo [ERROR] Invalid OKR_DATABASE_URL value.
echo        %OKR_DATABASE_URL%
exit /b 1

:wait_for_http
set "SERVICE_NAME=%~1"
set "SERVICE_URL=%~2"
set "MAX_RETRIES=%~3"
set /a RETRY_COUNT=0
:wait_for_http_loop
set /a RETRY_COUNT=RETRY_COUNT+1
rem Previous implementation used Invoke-WebRequest here, but python urlopen is more stable in tight batch loops.
"%PYEXE%" -c "import urllib.request; urllib.request.urlopen(r'%SERVICE_URL%', timeout=2)" >nul 2>&1
if not errorlevel 1 (
    echo [OK] %SERVICE_NAME% is reachable.
    exit /b 0
)
if /I "%SERVICE_NAME%"=="Backend API" (
    if defined BACKEND_PID (
        "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
            "try { $p = Get-Process -Id %BACKEND_PID% -ErrorAction Stop; if ($p) { exit 0 } ; exit 1 } catch { exit 1 }"
        if errorlevel 1 (
            echo [ERROR] Backend API process ^(PID %BACKEND_PID%^) exited before becoming ready.
            exit /b 1
        )
    ) else (
        "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
            "$p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { [string]$_.Name -ieq 'python.exe' -and [string]$_.CommandLine -match 'backend_app\\.run_api' }; if ($p) { exit 0 } else { exit 1 }"
        if errorlevel 1 (
            echo [ERROR] Backend API process exited before becoming ready.
            exit /b 1
        )
    )
)
if %RETRY_COUNT% geq %MAX_RETRIES% (
    echo [ERROR] %SERVICE_NAME% is not reachable at %SERVICE_URL%.
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
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
ping -n 2 127.0.0.1 >nul
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
    "$pidFile=[Environment]::GetEnvironmentVariable('SPAWN_PID_FILE');" ^
    "$lastPidFile=[Environment]::GetEnvironmentVariable('SPAWN_LAST_PID_FILE');" ^
    "try { $proc = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $cwd -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -PassThru -ErrorAction Stop; if ($pidFile) { Add-Content -Path $pidFile -Value ([string]$proc.Id) -Encoding Ascii }; if ($lastPidFile) { Set-Content -Path $lastPidFile -Value ([string]$proc.Id) -Encoding Ascii }; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
exit /b %ERRORLEVEL%

:set_last_spawned_pid_from_file
set "LAST_SPAWNED_PID="
if not exist "%LAST_PID_FILE%" exit /b 1
set /p LAST_SPAWNED_PID=<"%LAST_PID_FILE%"
if not defined LAST_SPAWNED_PID exit /b 1
exit /b 0

:stop_stale_hybrid_processes
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "$root = [string][Environment]::GetEnvironmentVariable('ROOT_CLEAN');" ^
    "$rootNorm = $root.ToLowerInvariant();" ^
    "$pidFile = [string][Environment]::GetEnvironmentVariable('PID_FILE');" ^
    "$regex = 'backend_app.run_api|backend_app.worker|spa-bff|spa-web\\\\node_modules\\\\.*next\\\\dist\\\\bin\\\\next|next start -- -p 3000|tsx watch';" ^
    "$currentPid = $PID;" ^
    "$byCommand = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $cmd = [string]$_.CommandLine; $name = [string]$_.Name; $cmdNorm = $cmd.ToLowerInvariant(); $_.ProcessId -ne $currentPid -and $cmd -and (($rootNorm -eq '') -or $cmdNorm.Contains($rootNorm)) -and ($name -in @('python.exe','node.exe','cmd.exe')) -and ($cmd -imatch $regex) } | Select-Object -ExpandProperty ProcessId;" ^
    "$byPort = @(); foreach ($port in @(8100, 3001, 3000)) { try { $byPort += (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess) } catch {} };" ^
    "$byPidFile = @(); if ($pidFile -and (Test-Path $pidFile)) { $byPidFile = Get-Content -Path $pidFile -ErrorAction SilentlyContinue | ForEach-Object { ($_ -as [int]) } | Where-Object { $_ -gt 0 } };" ^
    "$targets = @($byCommand + $byPort + $byPidFile) | Where-Object { $_ } | Sort-Object -Unique;" ^
    "foreach ($procId in $targets) { try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } catch {} };" ^
    "if ($pidFile) { try { Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue } catch {} }"
exit /b 0
