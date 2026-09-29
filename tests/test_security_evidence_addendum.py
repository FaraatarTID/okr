"""A `since_capture` addendum describes the working tree; it must never pass a control.

`docs/security/rate-limit.json`, `docs/security/csrf-origin.json` and
`docs/evidence/security-parity.json` are dated captures of `release-2026-09-14-bff`. The
origin guard and the BFF rate limiter exist now but are in no released build, so those
records carry an explicit `since_capture` note instead of being rewritten, which would
invent a capture. These tests keep that note from quietly becoming a substitute for one:
the status stays `pending` and the validators keep refusing the record.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_security_parity import validate_security_parity

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "security-parity.json"
ARTIFACTS = {
    "rate_limiting": ROOT / "docs" / "security" / "rate-limit.json",
    "csrf_and_origin_controls": ROOT / "docs" / "security" / "csrf-origin.json",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_an_addendum_never_accompanies_a_passed_status() -> None:
    for control, path in ARTIFACTS.items():
        artifact = _load(path)
        if "since_capture" in artifact:
            assert artifact["status"] == "pending", (
                f"{path.name}: an addendum describes uncaptured code, so the record "
                f"for {control} cannot be `passed`"
            )
            assert artifact["since_capture"]["status_of_record"] == "pending"
            assert artifact["since_capture"]["note"].startswith("This is not a capture")


def test_the_captured_observation_is_left_as_the_capture_recorded_it() -> None:
    """The addendum is additive: the dated `observed` text must keep its capture date."""
    for path in ARTIFACTS.values():
        artifact = _load(path)
        assert artifact["release_id"] == "release-2026-09-14-bff"
        assert artifact["captured_at"] == "2026-09-14T00:00:00Z"
        assert artifact["observed"].strip()


def test_the_summary_addendum_is_marked_as_not_a_capture() -> None:
    controls = {c["name"]: c for c in _load(EVIDENCE)["controls"]}
    for name in ARTIFACTS:
        control = controls[name]
        if "since_capture" in control:
            assert control["status"] == "pending"
            assert "not a capture" in control["since_capture"]


def test_the_validator_still_refuses_the_pending_record() -> None:
    errors = validate_security_parity(_load(EVIDENCE), base_dir=EVIDENCE.parent)
    assert "control rate_limiting status must be passed" in errors
    assert "control csrf_and_origin_controls status must be passed" in errors


def test_the_addendum_does_not_change_what_the_validator_accepts() -> None:
    """Stripping every addendum must not change the validator's verdict."""
    evidence = _load(EVIDENCE)
    with_addendum = validate_security_parity(evidence, base_dir=EVIDENCE.parent)
    for control in evidence["controls"]:
        control.pop("since_capture", None)
    without_addendum = validate_security_parity(evidence, base_dir=EVIDENCE.parent)
    assert with_addendum == without_addendum
