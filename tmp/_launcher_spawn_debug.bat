@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%~dp0"
set "VENV_DIR=.venv"
set "PYEXE=%ROOT%%VENV_DIR%\Scripts\python.exe"
set "POWERSHELL_EXE=powershell"
set "LOG_DIR=%ROOT%tmp\local-hybrid-logs"
set "BACKEND_OUT_LOG=%LOG_DIR%\_dbg_backend.out.log"
set "BACKEND_ERR_LOG=%LOG_DIR%\_dbg_backend.err.log"
set "BFF_OUT_LOG=%LOG_DIR%\_dbg_bff.out.log"
set "BFF_ERR_LOG=%LOG_DIR%\_dbg_bff.err.log"
set "SPA_OUT_LOG=%LOG_DIR%\_dbg_spa.out.log"
set "SPA_ERR_LOG=%LOG_DIR%\_dbg_spa.err.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
echo A
for /f %%P in ('%POWERSHELL_EXE% -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '%PYEXE%' -ArgumentList '-c','print(123)' -WorkingDirectory '%ROOT%' -RedirectStandardOutput '%BACKEND_OUT_LOG%' -RedirectStandardError '%BACKEND_ERR_LOG%' -WindowStyle Hidden -PassThru; $p.Id"') do set "BACKEND_PID=%%P"
echo B BACKEND_PID=%BACKEND_PID%
for /f %%P in ('%POWERSHELL_EXE% -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath 'npm.cmd' -ArgumentList '--version' -WorkingDirectory '%ROOT%spa-bff' -RedirectStandardOutput '%BFF_OUT_LOG%' -RedirectStandardError '%BFF_ERR_LOG%' -WindowStyle Hidden -PassThru; $p.Id"') do set "BFF_PID=%%P"
echo C BFF_PID=%BFF_PID%
for /f %%P in ('%POWERSHELL_EXE% -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath 'npm.cmd' -ArgumentList '--version' -WorkingDirectory '%ROOT%spa-web' -RedirectStandardOutput '%SPA_OUT_LOG%' -RedirectStandardError '%SPA_ERR_LOG%' -WindowStyle Hidden -PassThru; $p.Id"') do set "SPA_PID=%%P"
echo D SPA_PID=%SPA_PID%
exit /b 0
