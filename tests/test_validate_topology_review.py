from __future__ import annotations

import json

from scripts.validate_topology_review import validate_review


def _review() -> dict:
    return {
        "schema_version": 1,
        "release_id": "release-a",
        "captured_at": "2026-01-01T00:00:00Z",
        "operator": "operator",
        "topology": "bff",
        "decision": "retain_bff",
        "evidence": {
            category: {
                "status": "passed",
                "artifact": f"evidence/{category}.json",
                "summary": "reviewed",
            }
            for category in (
                "security_parity",
                "failure_isolation",
                "resource_overhead",
                "rollback_rehearsal",
            )
        },
    }


def test_complete_review_passes() -> None:
    assert validate_review(_review()) == []


def test_incomplete_review_reports_each_missing_category() -> None:
    review = _review()
    review["evidence"]["rollback_rehearsal"]["status"] = "pending"
    review["evidence"].pop("resource_overhead")

    errors = validate_review(review)

    assert "evidence.resource_overhead must be an object" in errors
    assert "evidence.rollback_rehearsal.status must be passed" in errors


def test_review_rejects_missing_or_escaping_artifacts(tmp_path) -> None:
    review = _review()
    review["evidence"]["security_parity"]["artifact"] = "../secret.json"
    review["evidence"]["failure_isolation"]["artifact"] = "missing.json"

    errors = validate_review(review, base_dir=tmp_path)

    assert "must stay below the review directory" in errors[0]
    assert any("does not exist: missing.json" in error for error in errors)


def test_review_validates_linked_category_artifacts(tmp_path) -> None:
    review = _review()
    artifact_dir = tmp_path / "evidence"
    artifact_dir.mkdir()
    for category in ("security_parity", "failure_isolation", "rollback_rehearsal"):
        review["evidence"][category]["artifact"] = f"evidence/{category}.json"
    review["evidence"]["resource_overhead"]["artifact"] = "evidence/comparison.json"
    (artifact_dir / "security_parity.json").write_text(
        json.dumps({"schema_version": 1, "release_id": "release-a", "captured_at": "2026-01-01T00:00:00Z", "operator": "operator", "topology": "bff", "controls": []}), encoding="utf-8"
    )
    (artifact_dir / "failure_isolation.json").write_text(
        json.dumps({"schema_version": 1, "release_id": "release-a", "captured_at": "2026-01-01T00:00:00Z", "operator": "operator", "topology": "bff", "scenarios": []}), encoding="utf-8"
    )
    (artifact_dir / "rollback_rehearsal.json").write_text(
        json.dumps({"schema_version": 1, "release_id": "release-a", "captured_at": "2026-01-01T00:00:00Z", "operator": "operator", "topology": "bff"}), encoding="utf-8"
    )
    (artifact_dir / "comparison.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "release-a",
                "captured_at": "2026-01-01T00:00:00Z",
                "operator": "operator",
                "topology": "comparison",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_review(review, base_dir=tmp_path)

    assert any("missing required control" in error for error in errors)
    assert any("missing required scenario" in error for error in errors)
    assert "resource_overhead artifact must contain resource_comparisons" in errors


def test_complete_review_and_specialized_artifacts_pass(tmp_path) -> None:
    review = _review()
    artifact_dir = tmp_path / "evidence"
    artifact_dir.mkdir()
    review["evidence"]["security_parity"]["artifact"] = "evidence/security.json"
    review["evidence"]["failure_isolation"]["artifact"] = "evidence/failure.json"
    review["evidence"]["resource_overhead"]["artifact"] = "evidence/comparison.json"
    review["evidence"]["rollback_rehearsal"]["artifact"] = "evidence/rollback.json"
    (artifact_dir / "security.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "release-a",
                "captured_at": "2026-01-01T00:00:00Z",
                "operator": "operator",
                "topology": "bff",
                "controls": [
                    {
                        "name": name,
                        "status": "passed",
                        "observed": "verified",
                        "artifact": "evidence/security-observation.json",
                    }
                    for name in (
                        "session_cookie_protection",
                        "csrf_and_origin_controls",
                        "actor_binding",
                        "request_signing",
                        "route_allowlisting",
                        "rate_limiting",
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "failure.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "release-a",
                "captured_at": "2026-01-01T00:00:00Z",
                "operator": "operator",
                "topology": "bff",
                "scenarios": [
                    {
                        "name": name,
                        "status": "passed",
                        "observed": "verified",
                        "artifact": "evidence/failure-observation.json",
                    }
                    for name in (
                        "bff_unavailable_api_reachable",
                        "api_unavailable_bff_reports_dependency_failure",
                        "worker_unavailable_api_remains_ready",
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "comparison.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "release-a",
                "captured_at": "2026-01-01T00:00:00Z",
                "operator": "operator",
                "topology": "comparison",
                "resource_comparisons": [
                    {
                        "container": "bff-1",
                        "baseline_cpu_percent": 2.0,
                        "candidate_cpu_percent": 1.5,
                        "cpu_delta_percent": -0.5,
                        "baseline_sample_count": 1,
                        "candidate_sample_count": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    for observation in (
        "security-observation.json",
        "failure-observation.json",
        "rollback-observation.json",
    ):
        (artifact_dir / observation).write_text("{}", encoding="utf-8")
    (artifact_dir / "rollback.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "release-a",
                "captured_at": "2026-01-01T00:00:00Z",
                "operator": "operator",
                "topology": "bff",
                "last_known_good_release": "release-a",
                "candidate_release": "release-b",
                "status": "passed",
                "restoration_duration_seconds": 10,
                "data_integrity": "verified",
                "artifact": "evidence/rollback-observation.json",
            }
        ),
        encoding="utf-8",
    )

    assert validate_review(review, base_dir=tmp_path) == []


def test_review_rejects_malformed_resource_comparison(tmp_path) -> None:
    review = _review()
    artifact_dir = tmp_path / "evidence"
    artifact_dir.mkdir()
    for category in review["evidence"]:
        review["evidence"][category]["artifact"] = f"evidence/{category}.json"
        (artifact_dir / f"{category}.json").write_text(
            json.dumps({"schema_version": 1, "release_id": "release-a", "captured_at": "2026-01-01T00:00:00Z", "operator": "operator", "topology": "bff"}),
            encoding="utf-8",
        )
    (artifact_dir / "resource_overhead.json").write_text(
            json.dumps({"schema_version": 1, "release_id": "release-a", "captured_at": "2026-01-01T00:00:00Z", "operator": "operator", "topology": "comparison", "resource_comparisons": [{"container": "bff-1", "cpu_delta_percent": "1.0"}]}),
        encoding="utf-8",
    )

    errors = validate_review(review, base_dir=tmp_path)

    assert "resource_comparisons[0].baseline_cpu_percent must be numeric" in errors
    assert "resource_comparisons[0].candidate_cpu_percent must be numeric" in errors


def test_review_rejects_artifact_from_another_release(tmp_path) -> None:
    review = _review()
    artifact_dir = tmp_path / "evidence"
    artifact_dir.mkdir()
    for category in review["evidence"]:
        review["evidence"][category]["artifact"] = f"evidence/{category}.json"
        (artifact_dir / f"{category}.json").write_text(
            json.dumps({"schema_version": 1, "release_id": "release-b"}), encoding="utf-8"
        )

    errors = validate_review(review, base_dir=tmp_path)

    assert "evidence.security_parity.artifact release_id must match the review" in errors
