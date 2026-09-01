@echo off
setlocal EnableExtensions

cd /d "%~dp0..\.."
set "ROOT=%~dp0..\..\"
set "ROOT_CLEAN=%ROOT%"
if "%ROOT_CLEAN:~-1%"=="\" set "ROOT_CLEAN=%ROOT_CLEAN:~0,-1%"
set "POWERSHELL_EXE=powershell"
set "LOG_DIR=%ROOT%tmp\local-hybrid-logs"
set "PID_FILE=%LOG_DIR%\local-hybrid.pids"

echo ==========================================
echo  OKR Tracker - Stop Local Hybrid Services
echo ==========================================
echo.
echo [1/2] Stopping backend + worker + BFF + SPA processes...

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

echo [2/2] Verifying listener ports...
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
    "$alive = @(); foreach ($port in @(8100,3001,3000)) { try { $alive += (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess) } catch {} }; if (@($alive).Count -gt 0) { Write-Host '[WARN] Some listeners still active:'; @($alive | Sort-Object -Unique) | ForEach-Object { Write-Host ('  PID ' + $_) } } else { Write-Host '[OK] Target ports are free.' }"

echo.
echo [DONE] Local hybrid stop command completed.
exit /b 0
