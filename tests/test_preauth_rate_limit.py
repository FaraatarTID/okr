"""The coarse per-peer bucket refuses a flood before any credential work is done.

Run against the real app and the real in-memory security store, not a stub, so a bucket that
was never consulted, or was keyed on something the caller controls, cannot pass. Each property
has a positive control next to it; without those, "the caller could not do X" would also be
true of a bucket that never ran.
"""

from __future__ import annotations

import secrets as _secrets

import pytest
from fastapi.testclient import TestClient

PROTECTED = "/v1/read/query"
TOKEN = "preauth-test-service-token"
LIMIT = 3
PEER = "203.0.113.50"
OTHER_PEER = "203.0.113.51"


@pytest.fixture()
def app(monkeypatch):
    import backend_app.main as backend_main
    from backend_app import security

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("OKR_BACKEND_PREAUTH_RATE_LIMIT_MAX_REQUESTS", str(LIMIT))
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    security._reset_security_state_for_tests()
    yield backend_main.app
    security._reset_security_state_for_tests()


def _client(app, peer: str = PEER) -> TestClient:
    return TestClient(app, client=(peer, 50000))


def _bad(client: TestClient, **extra: str):
    headers = {"x-okr-service-token": "wrong-" + _secrets.token_hex(4)}
    headers.update(extra)
    return client.post(PROTECTED, json={}, headers=headers)


def _statuses(client: TestClient, n: int, **extra: str) -> list[int]:
    return [_bad(client, **extra).status_code for _ in range(n)]


def test_wrong_tokens_get_401_until_the_bucket_is_spent_then_429(app):
    client = _client(app)
    assert _statuses(client, LIMIT + 3) == [401] * LIMIT + [429] * 3


def test_the_token_comparison_is_not_reached_once_the_bucket_is_spent(app, monkeypatch):
    """The point of running first: a guesser costs the server nothing after the bucket."""
    from backend_app import security

    calls = {"n": 0}
    real = security.secrets.compare_digest

    def counting(a, b):
        calls["n"] += 1
        return real(a, b)

    monkeypatch.setattr(security.secrets, "compare_digest", counting)
    client = _client(app)
    _statuses(client, LIMIT)
    assert calls["n"] == LIMIT, "positive control: each admitted request compares once"
    _statuses(client, 5)
    assert calls["n"] == LIMIT, "requests past the bucket must not reach the comparison"


def test_a_valid_token_from_a_spent_peer_is_also_refused(app):
    """It is a flood guard on the peer, so it applies to good credentials too.

    Stated as a test because it is the trade-off of this design, and a later change that
    exempted valid callers would quietly turn the bucket back into a post-auth one.
    """
    client = _client(app)
    _statuses(client, LIMIT)
    good = client.post(PROTECTED, json={}, headers={"x-okr-service-token": TOKEN})
    assert good.status_code == 429


def test_a_different_peer_is_unaffected_by_a_spent_peer(app):
    spent = _client(app, PEER)
    _statuses(spent, LIMIT + 2)
    assert _bad(spent).status_code == 429
    assert _bad(_client(app, OTHER_PEER)).status_code == 401


@pytest.mark.parametrize(
    "header",
    ["x-okr-client-ip", "x-forwarded-for", "x-real-ip", "forwarded"],
)
def test_the_caller_cannot_choose_its_bucket_with_a_header(app, header):
    client = _client(app)
    _statuses(client, LIMIT)
    rotated = [
        _bad(client, **{header: f"198.51.100.{i}"}).status_code for i in range(1, 6)
    ]
    assert rotated == [429] * 5, f"{header} let the caller escape the peer bucket"


def test_the_first_request_of_a_fresh_peer_is_admitted_to_the_credential_check(app):
    """Positive control for the rotation test: a bucket that never ran would also 'hold'."""
    assert _bad(_client(app, "203.0.113.99")).status_code == 401


def test_an_unavailable_security_store_fails_closed_with_503(app, monkeypatch):
    from backend_app import security

    def down(**_kwargs):
        raise security.SecurityStateUnavailableError("down")

    monkeypatch.setattr(security, "check_rate_limit", down)
    assert _bad(_client(app)).status_code == 503


def test_the_ceiling_is_read_from_configuration(monkeypatch):
    from backend_app.config import get_backend_settings

    monkeypatch.delenv("OKR_BACKEND_PREAUTH_RATE_LIMIT_MAX_REQUESTS", raising=False)
    assert get_backend_settings().preauth_rate_limit_max_requests == 60000
    monkeypatch.setenv("OKR_BACKEND_PREAUTH_RATE_LIMIT_MAX_REQUESTS", "17")
    assert get_backend_settings().preauth_rate_limit_max_requests == 17
    monkeypatch.setenv("OKR_BACKEND_PREAUTH_RATE_LIMIT_MAX_REQUESTS", "0")
    assert get_backend_settings().preauth_rate_limit_max_requests == 1


def test_the_bucket_and_the_per_client_bucket_do_not_share_a_key(app, monkeypatch):
    """Sequenced with the per-client limit so the two cannot conflict on one counter."""
    from backend_app import security

    keys: list[str] = []
    real = security.check_rate_limit

    def spy(*, key, **kwargs):
        keys.append(key)
        return real(key=key, **kwargs)

    monkeypatch.setattr(security, "check_rate_limit", spy)
    client = _client(app)
    client.post(
        PROTECTED,
        json={},
        headers={"x-okr-service-token": TOKEN, "x-okr-client-ip": "198.51.100.7"},
    )
    assert keys[0] == f"preauth:{PEER}"
    assert "ip:198.51.100.7" in keys
    assert len(set(keys)) == len(keys)


def test_the_configured_ceiling_and_window_reach_the_store(app, monkeypatch):
    """The store clamps a bad window to one second, so only the arguments can prove this."""
    from backend_app import security

    seen: list[tuple[str, int, int]] = []
    real = security.check_rate_limit

    def spy(*, key, limit, window_seconds):
        seen.append((key, limit, window_seconds))
        return real(key=key, limit=limit, window_seconds=window_seconds)

    monkeypatch.setattr(security, "check_rate_limit", spy)
    _bad(_client(app))
    assert seen[0] == (f"preauth:{PEER}", LIMIT, 3600)
