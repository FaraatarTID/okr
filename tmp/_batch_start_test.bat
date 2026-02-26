@echo off
setlocal
set "ROOT=c:\Users\Surface Book 2\Documents\GitHub\okr\"
set "LOG_DIR=%ROOT%tmp\local-hybrid-logs"
set "BACKEND_LOG=%LOG_DIR%\_batch_start_test.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if exist "%BACKEND_LOG%" del /q "%BACKEND_LOG%"
start "TEST" cmd /c "cd /d \"%ROOT%\" && echo hello > \"%BACKEND_LOG%\" 2>&1"
timeout /t 2 /nobreak >nul
if exist "%BACKEND_LOG%" (
  echo FOUND
  type "%BACKEND_LOG%"
) else (
  echo MISSING
)
