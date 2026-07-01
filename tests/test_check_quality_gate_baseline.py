from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_quality_gate_baseline.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_quality_gate_baseline", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
check_quality_gate_baseline = importlib.util.module_from_spec(SPEC)
sys.modules["check_quality_gate_baseline"] = check_quality_gate_baseline
SPEC.loader.exec_module(check_quality_gate_baseline)


def test_validate_baseline_expiry_passes_before_deadline():
    errors = check_quality_gate_baseline.validate_baseline_expiry(
        today=date(2026, 2, 24)
    )
    assert errors == []


def test_validate_baseline_expiry_fails_after_deadline():
    errors = check_quality_gate_baseline.validate_baseline_expiry(
        today=date(2026, 10, 1)
    )
    assert errors
    assert any("QG-001" in err for err in errors)
    assert any("QG-002" in err for err in errors)
