@echo off
setlocal

start "OKR Launcher" /B "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0..\okr-launcher-ui.ps1"

endlocal
