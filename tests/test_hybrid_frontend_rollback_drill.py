from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DRILL_PATH = ROOT / "docs" / "HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.json"


def _load_drill() -> dict[str, Any]:
    payload = json.loads(DRILL_PATH.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict), "Rollback drill payload must be a JSON object."
    return payload


def _parse_iso_datetime(value: Any) -> datetime:
    assert isinstance(value, str), f"Expected ISO datetime string, got {type(value)!r}."
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_hybrid_frontend_rollback_drill_top_level_shape() -> None:
    payload = _load_drill()

    for key in (
        "id",
        "date",
        "environment",
        "drill_type",
        "scope",
        "objective",
        "trigger",
        "timeline_utc",
        "mttr_minutes",
        "rollback_actions",
        "verification",
        "outcome",
        "gaps",
    ):
        assert key in payload

    assert isinstance(payload["id"], str) and payload["id"].strip()
    assert payload["drill_type"] == "staged"
    assert isinstance(payload["environment"], str) and payload["environment"].strip()
    assert isinstance(payload["objective"], str) and payload["objective"].strip()

    parsed_date = date.fromisoformat(str(payload["date"]))
    assert parsed_date.year >= 2026


def test_hybrid_frontend_rollback_drill_timeline_and_mttr_contract() -> None:
    payload = _load_drill()
    timeline = payload["timeline_utc"]
    assert isinstance(timeline, dict)

    incident_at = _parse_iso_datetime(timeline["incident_declared_at"])
    rollback_started_at = _parse_iso_datetime(timeline["rollback_started_at"])
    rollback_completed_at = _parse_iso_datetime(timeline["rollback_completed_at"])

    assert incident_at <= rollback_started_at <= rollback_completed_at

    mttr_minutes = int(payload["mttr_minutes"])
    assert mttr_minutes > 0
    measured_minutes = int((rollback_completed_at - incident_at).total_seconds() // 60)
    assert mttr_minutes == measured_minutes
    assert mttr_minutes <= 15


def test_hybrid_frontend_rollback_drill_has_actions_outcome_and_gaps() -> None:
    payload = _load_drill()

    scope = payload["scope"]
    assert isinstance(scope, dict)
    assert scope.get("mode") in {"scoped", "global"}
    assert isinstance(scope.get("team_ids"), list)
    assert isinstance(scope.get("usernames"), list)

    trigger = payload["trigger"]
    assert isinstance(trigger, dict)
    assert isinstance(trigger.get("kind"), str) and str(trigger["kind"]).strip()
    assert isinstance(trigger.get("details"), str) and str(trigger["details"]).strip()

    rollback_actions = payload["rollback_actions"]
    assert isinstance(rollback_actions, list) and len(rollback_actions) >= 3
    for action in rollback_actions:
        assert isinstance(action, str) and action.strip()

    verification = payload["verification"]
    assert isinstance(verification, list) and verification
    for item in verification:
        assert isinstance(item, str) and item.strip()

    outcome = payload["outcome"]
    assert isinstance(outcome, dict)
    assert outcome.get("rollback_successful") is True
    assert outcome.get("objective_met") is True

    gaps = payload["gaps"]
    assert isinstance(gaps, list) and gaps
    for gap in gaps:
        assert isinstance(gap, dict)
        assert isinstance(gap.get("id"), str) and str(gap["id"]).strip()
        assert gap.get("severity") in {"low", "medium", "high", "critical"}
        assert isinstance(gap.get("description"), str) and str(gap["description"]).strip()
        assert isinstance(gap.get("owner"), str) and str(gap["owner"]).strip()
        date.fromisoformat(str(gap["due_date"]))
