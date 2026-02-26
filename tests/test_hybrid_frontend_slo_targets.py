from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SLO_TARGETS_PATH = ROOT / "docs" / "HYBRID_FRONTEND_SLO_TARGETS.json"

REQUIRED_SLO_IDS = {
    "login_success_rate",
    "atlas_read_success_rate",
    "atlas_read_p95_latency_ms",
    "timer_mutation_success_rate",
    "timer_mutation_p95_latency_ms",
    "report_open_success_rate",
}


def _load_targets() -> dict[str, Any]:
    payload = json.loads(SLO_TARGETS_PATH.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict), "SLO targets payload must be a JSON object."
    return payload


def test_hybrid_frontend_slo_targets_top_level_shape() -> None:
    payload = _load_targets()

    for required in ("service", "version", "owner", "dashboard", "slos"):
        assert required in payload

    assert payload["service"] == "hybrid_frontend_migration"
    assert isinstance(payload["version"], str) and payload["version"].strip()

    owner = payload["owner"]
    assert isinstance(owner, dict)
    assert isinstance(owner.get("team"), str) and str(owner["team"]).strip()
    assert isinstance(owner.get("channel"), str) and str(owner["channel"]).strip()

    dashboard = payload["dashboard"]
    assert isinstance(dashboard, dict)
    assert isinstance(dashboard.get("name"), str) and str(dashboard["name"]).strip()
    assert isinstance(dashboard.get("refresh_seconds"), int)
    windows = dashboard.get("windows")
    assert isinstance(windows, list) and windows
    for window in windows:
        assert isinstance(window, dict)
        assert isinstance(window.get("name"), str) and str(window["name"]).strip()
        assert isinstance(window.get("duration_minutes"), int)
        assert int(window["duration_minutes"]) > 0


def test_hybrid_frontend_slo_targets_cover_required_journeys() -> None:
    payload = _load_targets()
    slos = payload.get("slos")
    assert isinstance(slos, list) and slos

    by_id: dict[str, dict[str, Any]] = {}
    for slo in slos:
        assert isinstance(slo, dict)
        slo_id = str(slo.get("id") or "").strip()
        assert slo_id
        assert slo_id not in by_id, f"Duplicate SLO id: {slo_id}"
        by_id[slo_id] = slo

    assert REQUIRED_SLO_IDS.issubset(by_id.keys())


def test_hybrid_frontend_slo_targets_threshold_contract() -> None:
    payload = _load_targets()
    slos = payload["slos"]
    by_id = {str(item["id"]): item for item in slos}

    for slo_id in REQUIRED_SLO_IDS:
        slo = by_id[slo_id]
        assert isinstance(slo.get("journey"), str) and str(slo["journey"]).strip()
        assert isinstance(slo.get("measurement_window_minutes"), int)
        assert int(slo["measurement_window_minutes"]) > 0
        assert isinstance(slo.get("queries"), dict) and slo["queries"]

        alerts = slo.get("alerts")
        assert isinstance(alerts, dict)
        assert isinstance(alerts.get("for_minutes"), int)
        assert int(alerts["for_minutes"]) > 0

        slo_type = str(slo.get("type") or "").strip()
        if slo_type == "success_rate":
            assert slo.get("unit") == "percent"
            target = float(slo["target"])
            warning = float(alerts["warning_below"])
            critical = float(alerts["critical_below"])
            assert 95.0 <= target <= 100.0
            assert warning <= target
            assert critical < warning
            assert "good" in slo["queries"] and "total" in slo["queries"]
            assert isinstance(slo["queries"]["good"], str)
            assert isinstance(slo["queries"]["total"], str)
        elif slo_type == "latency_p95":
            assert slo.get("unit") == "milliseconds"
            target = int(slo["target"])
            warning = int(alerts["warning_above"])
            critical = int(alerts["critical_above"])
            assert target > 0
            assert warning > target
            assert critical > warning
            assert "value" in slo["queries"]
            assert isinstance(slo["queries"]["value"], str)
        else:
            raise AssertionError(f"Unsupported SLO type for {slo_id}: {slo_type}")
