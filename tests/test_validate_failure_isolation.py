from __future__ import annotations

from scripts.validate_failure_isolation import validate_failure_isolation


def _evidence() -> dict:
    return {
        "schema_version": 1,
        "scenarios": [
            {
                "name": name,
                "status": "passed",
                "observed": "expected result",
                "artifact": f"evidence/{name}.json",
            }
            for name in (
                "bff_unavailable_api_reachable",
                "api_unavailable_bff_reports_dependency_failure",
                "worker_unavailable_api_remains_ready",
            )
        ],
    }


def test_complete_failure_isolation_evidence_passes() -> None:
    assert validate_failure_isolation(_evidence()) == []


def test_missing_or_failed_scenario_is_reported() -> None:
    evidence = _evidence()
    evidence["scenarios"] = evidence["scenarios"][:-1]
    evidence["scenarios"][0]["status"] = "failed"

    errors = validate_failure_isolation(evidence)

    assert "scenario bff_unavailable_api_reachable status must be passed" in errors
    assert "missing required scenario worker_unavailable_api_remains_ready" in errors


def test_failure_evidence_rejects_missing_artifact(tmp_path) -> None:
    evidence = _evidence()

    errors = validate_failure_isolation(evidence, base_dir=tmp_path)

    assert any(
        "does not exist: evidence" in error
        and "bff_unavailable_api_reachable.json" in error
        for error in errors
    )
