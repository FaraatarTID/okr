import os
from pathlib import Path
import sys
import tempfile


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "streamlit_app"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

_PYTEST_TEMP_DIR = ROOT_DIR / ".test-artifacts" / "pytest-subproc"
_PYTEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(_PYTEST_TEMP_DIR)
os.environ["TEMP"] = str(_PYTEST_TEMP_DIR)
tempfile.tempdir = str(_PYTEST_TEMP_DIR)
