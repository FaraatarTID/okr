from __future__ import annotations

from scripts.validate_security_parity import validate_security_parity


CONTROL_NAMES = (
    "session_cookie_protection",
    "csrf_and_origin_controls",
    "actor_binding",
    "request_signing",
    "route_allowlisting",
    "rate_limiting",
)


def _evidence() -> dict:
    return {
        "schema_version": 1,
        "controls": [
            {
                "name": name,
                "status": "passed",
                "observed": "expected rejection/acceptance observed",
                "artifact": f"evidence/security/{name}.json",
            }
            for name in CONTROL_NAMES
        ],
    }


def test_complete_security_parity_evidence_passes() -> None:
    assert validate_security_parity(_evidence()) == []


def test_missing_and_failed_controls_are_reported() -> None:
    evidence = _evidence()
    evidence["controls"] = evidence["controls"][:-1]
    evidence["controls"][0]["status"] = "failed"

    errors = validate_security_parity(evidence)

    assert "control session_cookie_protection status must be passed" in errors
    assert "missing required control rate_limiting" in errors
