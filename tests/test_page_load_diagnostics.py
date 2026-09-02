from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.diagnose_page_load import TraceError, analyze_trace


FIXTURE = Path(__file__).parent / "fixtures" / "page_load_trace.json"


def test_trace_fixture_exposes_unattributed_time_instead_of_guessing() -> None:
    result = analyze_trace(json.loads(FIXTURE.read_text(encoding="utf-8")))

    assert result["total_duration_ms"] == 10000.0
    assert result["stages_ms"] == {
        "browser": 900.0,
        "bff": 120.0,
        "backend": 1980.0,
        "database": 400.0,
        "unattributed": 6600.0,
    }
    assert result["dominant_stage"] == "unattributed"
    assert result["attribution_pct"] == 34.0
    assert result["diagnostic"] == "instrument the missing layer before optimizing"


def test_trace_identifies_dominant_instrumented_stage() -> None:
    result = analyze_trace(
        {
            "total_duration_ms": 1000,
            "spans": [
                {"stage": "browser", "duration_ms": 100},
                {"stage": "bff", "duration_ms": 100},
                {"stage": "backend", "duration_ms": 600},
                {"stage": "database", "duration_ms": 200},
            ],
        }
    )

    assert result["dominant_stage"] == "backend"
    assert result["attribution_pct"] == 100.0


@pytest.mark.parametrize(
    "trace, message",
    [
        ({"total_duration_ms": 0, "spans": []}, "total_duration_ms"),
        (
            {"total_duration_ms": 100, "spans": [{"stage": "worker", "duration_ms": 1}]},
            "stage",
        ),
        (
            {
                "total_duration_ms": 100,
                "spans": [{"stage": "database", "duration_ms": 101}],
            },
            "exceed",
        ),
    ],
)
def test_trace_rejects_incomplete_or_inconsistent_measurements(trace, message) -> None:
    with pytest.raises(TraceError, match=message):
        analyze_trace(trace)
