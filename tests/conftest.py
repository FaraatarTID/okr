import os
from pathlib import Path
import sys
import tempfile

os.environ["OKR_BACKEND_API_URL"] = ""
os.environ["OKR_BACKEND_ENFORCE_REQUEST_SIGNING"] = "false"
os.environ["OKR_BACKEND_ENFORCE_TOKEN"] = "false"
os.environ["OKR_DATA_ACCESS_MODE"] = "database"
os.environ["OKR_ENFORCE_STRONG_PASSWORD_POLICY"] = "false"
os.environ["OKR_STRICT_RUNTIME_PREFLIGHT"] = "false"
os.environ["ALLOW_EXTERNAL_AI"] = "false"

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OKR_DATABASE_URL"] = "sqlite:///:memory:"


ROOT_DIR = Path(__file__).resolve().parents[1]

for p in [str(ROOT_DIR)]:
    while p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, str(ROOT_DIR))


_PYTEST_TEMP_DIR = ROOT_DIR / ".test-artifacts" / "pytest-subproc"
_PYTEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(_PYTEST_TEMP_DIR)
os.environ["TEMP"] = str(_PYTEST_TEMP_DIR)
tempfile.tempdir = str(_PYTEST_TEMP_DIR)
