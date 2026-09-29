"""The security-parity probe must fail when a control is missing, not only pass when present.

A probe that reports `passed` against a stack without the control is worse than no probe:
it manufactures evidence. These tests run the probe against a simulated stack in which each
control can be switched off, and require the matching control to come back `failed`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.security_parity_probe import (
    CONTROL_NAMES,
    Response,
    Target,
    build_document,
    run_probe,
    write_evidence,
)
from scripts.validate_security_parity import validate_security_parity
from tests import _test_credentials

WEB, BFF, BACKEND = "http://web", "http://bff", "http://backend"
PROBE_PW = _test_credentials.test_password("security_parity_probe")
TARGET = Target(
    web_url=WEB,
    username="admin",
    password=PROBE_PW,
    bff_url=BFF,
    backend_url=BACKEND,
    service_token="tok",
    max_burst=100,
)


class FakeStack:
    """A stack that behaves like the released one unless a control is disabled."""

    def __init__(self, **disabled: bool) -> None:
        self.off = {name for name, value in disabled.items() if value}
        self.limit = 60
        self.hits: dict[str, int] = {}

    def __call__(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> Response:
        h = {k.lower(): v for k, v in headers.items()}
        if url.startswith(BACKEND):
            return self._backend(h)
        if url.startswith(BFF):
            return self._bff(url, h)
        return self._web(method, url, h)

    def _origin_refused(self, h: dict[str, str]) -> bool:
        if "origin" in self.off:
            return False
        if "originstrict" in self.off and h.get("cookie"):
            # a guard that also blocks same-origin state changes made with a session
            return True
        if "sec-fetch-site" in h:
            return h["sec-fetch-site"] not in {"same-origin", "none"}
        return "origin" in h and h["origin"] != "http://web"

    def _web(self, method: str, url: str, h: dict[str, str]) -> Response:
        path = url[len(WEB) :]
        if method != "GET" and self._origin_refused(h):
            # An unrelated 403 (a WAF, say) must not be mistaken for the origin guard.
            code = "FORBIDDEN" if "origincode" in self.off else "INVALID_ORIGIN"
            return Response(403, body={"code": code})
        if "gatewaydown" in self.off:
            return Response(502, body={"error": "BFF request failed."})
        if path == "/api/session/login":
            return self._login(h)
        if path.startswith("/api/backend/"):
            return self._backend_route(method, path[len("/api/backend") :], h)
        return Response(404)

    def _login(self, h: dict[str, str]) -> Response:
        key = h.get("x-okr-client-ip", "")
        if key:
            if "globallimit" in self.off:
                key = "shared"  # one bucket for everyone, so a burst throttles all clients
            self.hits[key] = self.hits.get(key, 0) + 1
            if "ratelimit" not in self.off and self.hits[key] > self.limit:
                headers = {} if "retryafter" in self.off else {"retry-after": "30"}
                return Response(429, headers=headers, body={"code": "RATE_LIMITED"})
        return Response(401, body={"code": "AUTH_INVALID_CREDENTIALS"})

    def _backend_route(self, method: str, path: str, h: dict[str, str]) -> Response:
        listed_out = path.startswith("/v1/not-a-route") or (
            path.startswith("/v1/state/") and "allowlist" not in self.off
        )
        if listed_out:
            code = (
                "FORBIDDEN" if "allowlistcode" in self.off else "ROUTE_NOT_ALLOWLISTED"
            )
            return Response(403, body={"code": code})
        if method == "POST" and "csrf" not in self.off:
            token = h.get("x-xsrf-token", "")
            if "csrfstrict" in self.off or not token or token != "csrf-value":
                code = "FORBIDDEN" if "csrfcode" in self.off else "INVALID_CSRF_TOKEN"
                return Response(403, body={"code": code})
        return Response(422, body={"code": "HTTP_422"})

    def _bff(self, url: str, h: dict[str, str]) -> Response:
        actor = h.get("x-okr-actor")
        if "actorstrict" in self.off:  # refuses even the session's own actor
            return Response(403, body={"code": "INVALID_ACTOR_HEADER"})
        if actor and actor != "admin" and "actor" not in self.off:
            code = "FORBIDDEN" if "actorcode" in self.off else "INVALID_ACTOR_HEADER"
            return Response(403, body={"code": code})
        return Response(422, body={"code": "HTTP_422"})

    def _backend(self, h: dict[str, str]) -> Response:
        if "signing" in self.off:
            return Response(200, body={})
        if h.get("x-okr-service-token") != "tok":
            return Response(401, body={"detail": "Unauthorized service token."})
        if not h.get("x-okr-signature"):
            return Response(401, body={"detail": "Missing signed request headers."})
        return Response(401, body={"detail": "Invalid request signature."})


class LoginAwareStack(FakeStack):
    """Same, but a good login issues cookies, as the real BFF does."""

    def _login(self, h: dict[str, str]) -> Response:
        if h.get("x-okr-client-ip"):
            return super()._login(h)
        flags = ["HttpOnly", "SameSite=Lax", "Max-Age=3600"]
        for gone, flag in (
            ("nohttponly", "HttpOnly"),
            ("nosamesite", "SameSite=Lax"),
            ("nomaxage", "Max-Age=3600"),
        ):
            if gone in self.off:
                flags.remove(flag)
        attrs = "".join(f"; {flag}" for flag in flags)
        return Response(
            200,
            set_cookies=[
                f"okr_spa_session=sess{attrs}",
                "okr_csrf_token=csrf-value; SameSite=Strict; Max-Age=3600",
            ],
            body={"success": True},
        )


def _statuses(stack: FakeStack, target: Target = TARGET) -> dict[str, str]:
    return {c["name"]: c["status"] for c in run_probe(target, stack)}


def test_a_stack_with_every_control_passes_every_control() -> None:
    statuses = _statuses(LoginAwareStack())
    assert list(statuses) == list(CONTROL_NAMES)
    assert set(statuses.values()) == {"passed"}


@pytest.mark.parametrize(
    ("disabled", "control"),
    [
        ("nohttponly", "session_cookie_protection"),
        ("nosamesite", "session_cookie_protection"),
        ("nomaxage", "session_cookie_protection"),
        ("origin", "csrf_and_origin_controls"),
        ("originstrict", "csrf_and_origin_controls"),
        ("origincode", "csrf_and_origin_controls"),
        ("csrf", "csrf_and_origin_controls"),
        ("csrfstrict", "csrf_and_origin_controls"),
        ("csrfcode", "csrf_and_origin_controls"),
        ("actor", "actor_binding"),
        ("actorstrict", "actor_binding"),
        ("actorcode", "actor_binding"),
        ("signing", "request_signing"),
        ("allowlist", "route_allowlisting"),
        ("allowlistcode", "route_allowlisting"),
        ("ratelimit", "rate_limiting"),
        ("retryafter", "rate_limiting"),
        ("globallimit", "rate_limiting"),
    ],
)
def test_a_missing_control_is_reported_failed(disabled: str, control: str) -> None:
    """Break exactly one behaviour: exactly its control fails and nothing else does."""
    statuses = _statuses(LoginAwareStack(**{disabled: True}))
    assert statuses[control] == "failed", f"{disabled} off but {control} did not fail"
    others = {name: status for name, status in statuses.items() if name != control}
    assert set(others.values()) == {"passed"}, f"{disabled} bled into: {others}"


def test_an_unreachable_stack_does_not_pass() -> None:
    def down(*_: object) -> Response:
        return Response(502, body={"error": "BFF request failed."})

    statuses = _statuses(down)  # type: ignore[arg-type]
    assert "passed" not in statuses.values()


def test_a_control_whose_target_is_missing_is_not_observed_not_passed() -> None:
    bare = Target(web_url=WEB, username="admin", password=PROBE_PW, max_burst=100)
    statuses = _statuses(LoginAwareStack(), bare)
    assert statuses["actor_binding"] == "not_observed"
    assert statuses["request_signing"] == "not_observed"
    assert statuses["rate_limiting"] == "passed"


def test_a_missing_service_token_keeps_the_token_checks_but_drops_the_signature_ones() -> (
    None
):
    no_token = Target(
        web_url=WEB,
        username="admin",
        password=PROBE_PW,
        bff_url=BFF,
        backend_url=BACKEND,
        max_burst=100,
    )
    controls = {c["name"]: c for c in run_probe(no_token, LoginAwareStack())}
    checks = [c["check"] for c in controls["request_signing"]["checks"]]
    assert len(checks) == 2
    assert not any("signature" in check for check in checks)


def _capture(tmp_path: Path) -> Path:
    document = build_document(
        run_probe(TARGET, LoginAwareStack()),
        release_id="release-test",
        operator="test-operator",
        topology="bff",
        notes=["a note"],
        captured_at="2026-01-01T00:00:00Z",
    )
    write_evidence(
        document,
        evidence_dir=tmp_path,
        artifact_dir="security-test",
        summary="security-parity-test.json",
    )
    return tmp_path / "security-parity-test.json"


def test_a_passing_capture_satisfies_the_repository_validator(tmp_path: Path) -> None:
    summary = _capture(tmp_path)
    evidence = json.loads(summary.read_text(encoding="utf-8"))
    assert validate_security_parity(evidence, base_dir=tmp_path) == []


def test_a_failing_capture_is_refused_by_the_repository_validator(
    tmp_path: Path,
) -> None:
    document = build_document(
        run_probe(TARGET, LoginAwareStack(ratelimit=True)),
        release_id="release-test",
        operator="test-operator",
        topology="bff",
        notes=[],
        captured_at="2026-01-01T00:00:00Z",
    )
    write_evidence(
        document,
        evidence_dir=tmp_path,
        artifact_dir="security-test",
        summary="security-parity-test.json",
    )
    evidence = json.loads((tmp_path / "security-parity-test.json").read_text("utf-8"))
    errors = validate_security_parity(evidence, base_dir=tmp_path)
    assert "control rate_limiting status must be passed" in errors


def test_the_capture_records_no_credential_cookie_or_body(tmp_path: Path) -> None:
    summary = _capture(tmp_path)
    text = summary.read_text(encoding="utf-8") + "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "security-test").glob("*.json")
    )
    for secret in ("csrf-value", "sess", "pw", "tok"):
        assert f'"{secret}"' not in text
    assert "csrf-value" not in text
    assert "okr_spa_session=sess" not in text


def test_a_gateway_error_never_counts_as_getting_past_a_gate() -> None:
    from scripts.security_parity_probe import _refuse

    bad_gateway = Response(502, body={"error": "BFF request failed."})
    assert not _refuse("x", bad_gateway, not_code="INVALID_ORIGIN").passed
    assert _refuse("x", Response(422, body={"code": "HTTP_422"}), not_code="A").passed
    assert not _refuse("x", Response(403, body={"code": "A"}), not_code="A").passed


def test_every_artifact_records_the_status_the_probe_observed(tmp_path: Path) -> None:
    document = build_document(
        run_probe(TARGET, LoginAwareStack(ratelimit=True)),
        release_id="release-test",
        operator="test-operator",
        topology="bff",
        notes=[],
        captured_at="2026-01-01T00:00:00Z",
    )
    write_evidence(
        document,
        evidence_dir=tmp_path,
        artifact_dir="security-test",
        summary="security-parity-test.json",
    )
    summary = json.loads((tmp_path / "security-parity-test.json").read_text("utf-8"))
    for control in summary["controls"]:
        artifact = json.loads((tmp_path / control["artifact"]).read_text("utf-8"))
        assert artifact["status"] == control["status"], control["name"]
        assert artifact["control"] == control["name"]
    statuses = {c["name"]: c["status"] for c in summary["controls"]}
    assert statuses["rate_limiting"] == "failed"


def test_the_capture_time_is_when_the_probe_ran_not_a_fixed_date() -> None:
    from datetime import UTC, datetime

    before = datetime.now(UTC).replace(microsecond=0)
    document = build_document(
        [], release_id="r", operator="o", topology="bff", notes=[]
    )
    after = datetime.now(UTC)
    stamped = datetime.fromisoformat(document["captured_at"].replace("Z", "+00:00"))
    assert before <= stamped <= after


def test_the_capture_states_what_the_checks_could_not_observe() -> None:
    from scripts.security_parity_probe import capture_notes

    text = " ".join(capture_notes(TARGET, ["operator note"]))
    assert "operator note" in text
    assert "plain HTTP" in text and "Secure cookie attribute was not observed" in text
    assert "X-OKR-Client-IP" in text
    https = Target(
        web_url="https://web",
        username="a",
        password=PROBE_PW,
        bff_url=BFF,
        backend_url=BACKEND,
        service_token="t",
    )
    assert "plain HTTP" not in " ".join(capture_notes(https, []))
    bare = Target(web_url="https://web", username="a", password=PROBE_PW)
    joined = " ".join(capture_notes(bare, []))
    assert "actor_binding was not observed" in joined
    assert "request_signing was not observed" in joined


def test_written_evidence_uses_lf_line_endings(tmp_path: Path) -> None:
    """The repository is LF. Python writes CRLF on Windows unless told otherwise."""
    summary = _capture(tmp_path)
    for path in [summary, *(tmp_path / "security-test").glob("*.json")]:
        assert b"\r" not in path.read_bytes(), path.name
