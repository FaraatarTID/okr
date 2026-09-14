from __future__ import annotations

from scripts.validate_rollback_rehearsal import validate_rollback_rehearsal


def _evidence() -> dict:
    return {
        "schema_version": 1,
        "last_known_good_release": "release-a",
        "candidate_release": "release-b",
        "status": "passed",
        "restoration_duration_seconds": 42.5,
        "data_integrity": "verified",
        "artifact": "evidence/rollback/rehearsal.json",
    }


def test_complete_rollback_evidence_passes() -> None:
    assert validate_rollback_rehearsal(_evidence()) == []


def test_rollback_requires_integrity_and_duration() -> None:
    evidence = _evidence()
    evidence["data_integrity"] = "unknown"
    evidence["restoration_duration_seconds"] = -1

    errors = validate_rollback_rehearsal(evidence)

    assert "restoration_duration_seconds must be non-negative" in errors
    assert "data_integrity must be verified" in errors
