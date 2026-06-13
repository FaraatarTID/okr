import os
from pathlib import Path
import sys
import tempfile

os.environ["OKR_BACKEND_API_URL"] = ""

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
