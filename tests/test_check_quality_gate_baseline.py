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


def test_empty_baseline_has_no_expiry_errors():
    errors = check_quality_gate_baseline.validate_baseline_expiry()
    assert errors == []


def test_validate_baseline_expiry_rejects_injected_expired_item(monkeypatch):
    expired_item = check_quality_gate_baseline.BaselineItem(
        id="TEST-EXPIRED",
        scope="injected expired item",
        rationale="the generic expiry rule must keep applying after QG-002 closes",
        expires_on=date(2026, 11, 30),
    )
    monkeypatch.setattr(check_quality_gate_baseline, "BASELINE_ITEMS", (expired_item,))

    errors = check_quality_gate_baseline.validate_baseline_expiry(
        today=date(2026, 12, 1)
    )
    assert len(errors) == 1
    assert "TEST-EXPIRED" in errors[0]


def test_closed_quality_gates_are_not_active_baseline_items():
    """QG-001 and QG-002 must stay out of the active expiry registry."""
    ids = [item.id for item in check_quality_gate_baseline.BASELINE_ITEMS]
    assert "QG-001" not in ids
    assert "QG-002" not in ids
