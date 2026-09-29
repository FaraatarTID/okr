"""The committed ef18d7f capture must stay a real, complete, honest record.

`docs/evidence/security-parity-ef18d7f.json` was produced by `scripts/security_parity_probe.py`
against the released image digests. These tests stop it drifting into something the probe could
not have written: a hand-edited status, a missing control, a credential, or a lost caveat.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.security_parity_probe import ARTIFACT_NAMES, CONTROL_NAMES
from scripts.validate_security_parity import validate_security_parity

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "evidence"
SUMMARY = EVIDENCE / "security-parity-ef18d7f.json"
NEGATIVE = EVIDENCE / "security-parity-6150b4a-negative-control.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_capture_satisfies_the_repository_validator() -> None:
    assert validate_security_parity(_load(SUMMARY), base_dir=EVIDENCE) == []


def test_every_control_is_present_and_backed_by_its_own_artifact() -> None:
    summary = _load(SUMMARY)
    assert [c["name"] for c in summary["controls"]] == list(CONTROL_NAMES)
    for control in summary["controls"]:
        artifact = _load(EVIDENCE / control["artifact"])
        assert control["artifact"].endswith(ARTIFACT_NAMES[control["name"]])
        assert artifact["control"] == control["name"]
        assert artifact["status"] == control["status"] == "passed"
        assert artifact["release_id"] == summary["release_id"]
        assert artifact["captured_at"] == summary["captured_at"]
        assert artifact["checks"], control["name"]
        assert all(check["passed"] for check in artifact["checks"]), control["name"]


def test_the_capture_names_the_release_it_observed_and_says_what_it_is_not() -> None:
    summary = _load(SUMMARY)
    assert summary["release_id"] == "release-ef18d7f-bff"
    assert summary["captured_at"] != "2026-09-14T00:00:00Z"
    notes = " ".join(summary["capture_notes"])
    assert "ef18d7f65e4f1ef8829cda3819fe49c8ba204cfa" in notes
    assert "Not a production or staging deployment" in notes
    assert "plain HTTP" in notes
    assert "X-OKR-Client-IP" in notes
    assert "no named human operator" in summary["operator"]


def test_the_capture_holds_no_credential_or_cookie_value() -> None:
    files = [SUMMARY, NEGATIVE, *(EVIDENCE / "security-ef18d7f").glob("*.json")]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"okr_spa_session=[A-Za-z0-9]", text), path.name
        assert "Set-Cookie" not in text, path.name
        assert "\r" not in text, path.name


def test_the_negative_control_shows_the_probe_can_fail() -> None:
    negative = _load(NEGATIVE)
    statuses = {c["name"]: c["status"] for c in negative["controls"]}
    assert statuses["csrf_and_origin_controls"] == "failed"
    assert statuses["route_allowlisting"] == "failed"
    assert statuses["rate_limiting"] == "failed"
    assert "NEGATIVE CONTROL, not release evidence" in " ".join(
        negative["capture_notes"]
    )
    assert negative["release_id"] != _load(SUMMARY)["release_id"]


def test_the_older_release_records_still_refuse_to_validate() -> None:
    """release-2026-09-14-bff lacked two controls; its records must not be upgraded."""
    old = _load(EVIDENCE / "security-parity.json")
    errors = validate_security_parity(old, base_dir=EVIDENCE)
    assert any("csrf_and_origin_controls" in e for e in errors)
    assert any("rate_limiting" in e for e in errors)
    for name in ("rate-limit.json", "csrf-origin.json"):
        record = _load(EVIDENCE.parent / "security" / name)
        assert record["status"] == "pending"
        addendum = record["since_capture"]
        assert addendum["superseded_by"] == "docs/evidence/security-parity-ef18d7f.json"
        assert addendum["status_of_record"] == "pending"
