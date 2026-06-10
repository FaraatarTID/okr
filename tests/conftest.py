import os
from pathlib import Path
import sys
import tempfile

os.environ["OKR_BACKEND_API_URL"] = ""

# 🚨 CRITICAL: Globally isolate database connections to an in-memory SQLite database
# to prevent any tests or migrations from attempting live calls to Supabase.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OKR_DATABASE_URL"] = "sqlite:///:memory:"


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "streamlit_app"

# Ensure ROOT_DIR is at the absolute front of sys.path to prevent streamlit_app/src shadowing root src
for p in [str(APP_DIR), str(ROOT_DIR)]:
    while p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(ROOT_DIR))


_PYTEST_TEMP_DIR = ROOT_DIR / ".test-artifacts" / "pytest-subproc"
_PYTEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(_PYTEST_TEMP_DIR)
os.environ["TEMP"] = str(_PYTEST_TEMP_DIR)
tempfile.tempdir = str(_PYTEST_TEMP_DIR)

