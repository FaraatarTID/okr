@echo off
setlocal
set "OKR_SECRETS_FILE=streamlit_app\.streamlit\secrets.toml"
for /f "usebackq delims=" %%U in (`python -c "import os,pathlib,tomllib; p=pathlib.Path(os.environ.get('OKR_SECRETS_FILE','')); d=tomllib.load(p.open('rb')) if p.exists() else {}; db=d.get('OKR_DATABASE_URL') or d.get('DATABASE_URL') or ((d.get('database') or {}).get('url')) or ''; print(str(db).strip())" 2^>nul`) do set "DB_URL_CANDIDATE=%%U"
echo DB_URL_CANDIDATE=%DB_URL_CANDIDATE%
