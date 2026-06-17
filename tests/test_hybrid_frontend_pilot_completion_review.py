from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT / "docs" / "HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.json"
SLO_TARGETS_PATH = ROOT / "docs" / "HYBRID_FRONTEND_SLO_TARGETS.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict)
    return payload


def _required_slo_targets() -> dict[str, dict[str, Any]]:
    targets = _load_json(SLO_TARGETS_PATH)
    slos = targets.get("slos")
    assert isinstance(slos, list) and slos
    result: dict[str, dict[str, Any]] = {}
    for slo in slos:
        assert isinstance(slo, dict)
        slo_id = str(slo.get("id") or "").strip()
        assert slo_id
        result[slo_id] = slo
    return result


def test_hybrid_frontend_pilot_review_top_level_shape() -> None:
    payload = _load_json(REVIEW_PATH)
    for key in (
        "id",
        "date",
        "target_source",
        "review_scope",
        "weekly_cycles",
        "summary",
        "recommendation",
        "approvals",
    ):
        assert key in payload

    assert isinstance(payload["id"], str) and payload["id"].strip()
    parsed_date = date.fromisoformat(str(payload["date"]))
    assert parsed_date == date(2026, 2, 25)

    review_scope = payload["review_scope"]
    assert isinstance(review_scope, dict)
    assert isinstance(review_scope.get("environment"), str) and str(
        review_scope["environment"]
    ).strip()
    cohorts = review_scope.get("cohorts")
    assert isinstance(cohorts, list) and len(cohorts) >= 2


def test_hybrid_frontend_pilot_review_has_two_stable_weekly_cycles() -> None:
    payload = _load_json(REVIEW_PATH)
    cycles = payload["weekly_cycles"]
    assert isinstance(cycles, list)
    assert len(cycles) >= 2

    previous_end: date | None = None
    for cycle in cycles:
        assert isinstance(cycle, dict)
        start_date = date.fromisoformat(str(cycle["start_date"]))
        end_date = date.fromisoformat(str(cycle["end_date"]))
        assert start_date <= end_date
        assert (end_date - start_date).days >= 6  # weekly window
        if previous_end is not None:
            assert start_date > previous_end
        previous_end = end_date

    summary = payload["summary"]
    assert isinstance(summary, dict)
    assert int(summary["stable_cycles_at_target"]) >= 2
    assert summary["all_required_slos_met"] is True


def test_hybrid_frontend_pilot_review_meets_all_required_slo_targets() -> None:
    payload = _load_json(REVIEW_PATH)
    required_targets = _required_slo_targets()
    required_ids = set(required_targets.keys())

    for cycle in payload["weekly_cycles"]:
        slo_results = cycle.get("slo_results")
        assert isinstance(slo_results, list) and slo_results

        by_id: dict[str, dict[str, Any]] = {}
        for result in slo_results:
            assert isinstance(result, dict)
            slo_id = str(result.get("id") or "").strip()
            assert slo_id and slo_id not in by_id
            by_id[slo_id] = result

        assert required_ids.issubset(by_id.keys())

        for slo_id in required_ids:
            result = by_id[slo_id]
            target = required_targets[slo_id]
            assert result["type"] == target["type"]
            assert result["unit"] == target["unit"]
            assert result["met_target"] is True

            expected_target = target["target"]
            assert float(result["target"]) == float(expected_target)
            actual = float(result["actual"])
            comparator = str(result["comparator"])
            if comparator == ">=":
                assert actual >= float(expected_target)
            elif comparator == "<=":
                assert actual <= float(expected_target)
            else:
                raise AssertionError(f"Unsupported comparator for {slo_id}: {comparator}")


def test_hybrid_frontend_pilot_review_recommendation_and_approvals() -> None:
    payload = _load_json(REVIEW_PATH)
    recommendation = payload["recommendation"]
    assert isinstance(recommendation, dict)
    assert recommendation.get("decision") == "proceed_cutover"
    date.fromisoformat(str(recommendation["effective_date"]))
    rationale = recommendation.get("rationale")
    guardrails = recommendation.get("guardrails")
    assert isinstance(rationale, list) and rationale
    assert isinstance(guardrails, list) and guardrails

    approvals = payload["approvals"]
    assert isinstance(approvals, list) and len(approvals) >= 3
    for approval in approvals:
        assert isinstance(approval, dict)
        assert isinstance(approval.get("role"), str) and str(approval["role"]).strip()
        assert approval.get("status") == "approved"
        approved_at = approval.get("approved_at")
        assert isinstance(approved_at, str) and approved_at.strip()
        datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
