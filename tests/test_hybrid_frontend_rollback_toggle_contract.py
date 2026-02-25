from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.json"
PLAYBOOK_PATH = ROOT / "docs" / "HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md"
ROLLOUT_ROUTE_PATH = ROOT / "spa-web" / "src" / "app" / "api" / "rollout" / "route.ts"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict)
    return payload


def test_rollback_toggle_contract_shape() -> None:
    payload = _load_json(CONTRACT_PATH)

    for key in (
        "id",
        "date",
        "work_item",
        "primary_toggle",
        "scoped_controls",
        "verification",
        "rollback_objective",
        "operator_flow",
        "result",
    ):
        assert key in payload

    assert payload["work_item"] == "HFM-001"
    assert date.fromisoformat(str(payload["date"])) == date(2026, 2, 25)


def test_rollback_toggle_contract_matches_rollout_policy_surface() -> None:
    payload = _load_json(CONTRACT_PATH)
    primary = payload["primary_toggle"]
    assert isinstance(primary, dict)
    assert primary.get("key") == "OKR_SPA_ROLLOUT_ENABLED"
    assert str(primary.get("rollback_value")).lower() == "false"

    scoped_controls = payload["scoped_controls"]
    assert isinstance(scoped_controls, list) and scoped_controls
    expected_keys = {
        "OKR_SPA_ROLLOUT_TEAM_IDS",
        "OKR_SPA_ROLLOUT_USERNAMES",
        "OKR_SPA_ROLLOUT_ROLES",
    }
    assert {str(item["key"]) for item in scoped_controls} == expected_keys

    route_source = ROLLOUT_ROUTE_PATH.read_text(encoding="utf-8")
    for key in expected_keys.union({"OKR_SPA_ROLLOUT_ENABLED"}):
        assert key in route_source

    verification = payload["verification"]
    assert isinstance(verification, dict)
    assert verification.get("endpoint") == "GET /api/rollout"
    expected = verification.get("expected")
    assert isinstance(expected, dict)
    assert expected.get("enabled") is False

    objective = payload["rollback_objective"]
    assert isinstance(objective, dict)
    assert int(objective["target_mttr_minutes"]) <= 15
    evidence_ref = ROOT / str(objective["evidence_reference"])
    assert evidence_ref.exists()

    result = payload["result"]
    assert isinstance(result, dict)
    assert result.get("acceptance_met") is True


def test_rollback_toggle_contract_is_aligned_with_playbook_target() -> None:
    playbook = PLAYBOOK_PATH.read_text(encoding="utf-8")
    assert "OKR_SPA_ROLLOUT_ENABLED=false" in playbook
    assert "less than 15 minutes" in playbook
