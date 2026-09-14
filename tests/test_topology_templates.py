from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_failure_isolation import REQUIRED_SCENARIOS
from scripts.validate_security_parity import REQUIRED_CONTROLS

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / "docs" / "templates" / name).read_text(encoding="utf-8"))


def test_security_template_covers_every_required_control() -> None:
    template = _load("security-parity.example.json")

    assert {item["name"] for item in template["controls"]} == REQUIRED_CONTROLS
    assert all(item["status"] == "pending" for item in template["controls"])


def test_failure_template_covers_every_required_scenario() -> None:
    template = _load("failure-isolation.example.json")

    assert {item["name"] for item in template["scenarios"]} == REQUIRED_SCENARIOS
    assert all(item["status"] == "pending" for item in template["scenarios"])


def test_topology_review_template_covers_all_categories() -> None:
    template = _load("topology-review.example.json")

    assert set(template["evidence"]) == {
        "security_parity",
        "failure_isolation",
        "resource_overhead",
        "rollback_rehearsal",
    }
    assert all(item["status"] == "pending" for item in template["evidence"].values())
