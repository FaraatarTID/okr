@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "DOCKER_ENV_FILE=deploy\docker\.env"
set "SECRETS_FILE=streamlit_app\.streamlit\secrets.toml"
set "DB_URL_CANDIDATE=%OKR_DATABASE_URL%"
set "OKR_DATABASE_URL="
if defined DB_URL_CANDIDATE call :accept "%DB_URL_CANDIDATE%" "env:OKR_DATABASE_URL"
if not defined OKR_DATABASE_URL if defined DATABASE_URL call :accept "%DATABASE_URL%" "env:DATABASE_URL"
set "DB_URL_CANDIDATE="
if not defined OKR_DATABASE_URL if exist "%DOCKER_ENV_FILE%" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%DOCKER_ENV_FILE%") do (
    if /I "%%A"=="OKR_DATABASE_URL" if not "%%B"=="" if not defined DB_URL_CANDIDATE set "DB_URL_CANDIDATE=%%~B"
    if /I "%%A"=="DATABASE_URL" if not "%%B"=="" if not defined DB_URL_CANDIDATE set "DB_URL_CANDIDATE=%%~B"
  )
  echo dotenv=[%DB_URL_CANDIDATE%]
  if defined DB_URL_CANDIDATE call :accept "%DB_URL_CANDIDATE%" "%DOCKER_ENV_FILE%"
)
set "DB_URL_CANDIDATE="
if not defined OKR_DATABASE_URL if exist "%SECRETS_FILE%" (
  set "OKR_SECRETS_FILE=%SECRETS_FILE%"
  for /f "usebackq delims=" %%U in (`python -c "import os,pathlib,tomllib; p=pathlib.Path(os.environ.get('OKR_SECRETS_FILE','')); d=tomllib.load(p.open('rb')) if p.exists() else {}; db=d.get('OKR_DATABASE_URL') or d.get('DATABASE_URL') or ((d.get('database') or {}).get('url')) or ''; print(str(db).strip())" 2^>nul`) do set "DB_URL_CANDIDATE=%%U"
  echo secrets=[%DB_URL_CANDIDATE%]
  if defined DB_URL_CANDIDATE call :accept "%DB_URL_CANDIDATE%" "%SECRETS_FILE%"
)
echo FINAL OKR_DATABASE_URL=[%OKR_DATABASE_URL%]
exit /b
:accept
set "DB_URL_CANDIDATE=%~1"
set "DB_URL_SOURCE=%~2"
set "OKR_DB_URL_CANDIDATE=%DB_URL_CANDIDATE%"
for /f "usebackq delims=" %%R in (`python -c "import os; from urllib.parse import urlparse; u=str(os.environ.get('OKR_DB_URL_CANDIDATE','')).strip(); up=u.upper(); host=(urlparse(u).hostname or '').lower() if u else ''; print('placeholder' if any(t in up for t in ('PROJECT_REF','DB_PASSWORD','AWS-0-REGION','CHANGE_ME')) else ('docker_internal' if host in ('db','postgres','backend-api') else ('empty' if not u else 'ok')))"`) do set "DB_URL_CHECK=%%R"
echo src=%DB_URL_SOURCE% check=%DB_URL_CHECK%
if /I "%DB_URL_CHECK%"=="ok" (
 set "OKR_DATABASE_URL=%DB_URL_CANDIDATE%"
)
exit /b
