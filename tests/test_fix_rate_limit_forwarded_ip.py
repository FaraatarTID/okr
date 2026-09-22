"""Rate-limit key isolation, and the BFF's session-header forwarding.

Three source-substring tests were removed from this file. Two asserted that
`backend_app/security.py` mentions `x_forwarded_for` and `forwarded`/`client_ip`; the
third asserted that `spa-bff/src/proxy.ts` mentions `x-forwarded-for`. After the
behaviour they described was deliberately removed, all three still passed - on comment
text, since the comments explaining that those headers are NOT read are what contained
the strings. They therefore certified the inverse of the shipped design, which is worse
than certifying nothing.

Their intended properties are covered behaviourally, and were checked before deletion
rather than assumed:
- a caller-supplied forwarding header cannot choose the rate-limit key, while the
  trusted private header does, and an absent private header falls back to the peer:
  `tests/test_rate_limit_key_trust.py`;
- the login lockout keys on the trusted address, both forwarding headers are rejected
  with a valid control in the same request, and an absent trusted address leaves the IP
  dimension inert while the account dimension still records and still enforces:
  `tests/test_login_throttle_key.py`;
- the BFF forwards the private client-IP header to the backend, omits it when the edge
  did not set it, and drops X-Forwarded-For and X-Real-IP even when present:
  `spa-bff/test/forwarded_ip.test.ts`.

Neither test kept below is a substring check of the kind that was removed.
"""

from pathlib import Path

from backend_app.rate_limiter import check_rate_limit

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVER_TS = _PROJECT_ROOT / "spa-bff" / "src" / "server.ts"


def test_rate_limit_uses_forwarded_ip_for_isolation():
    """Different keys get independent rate limits."""
    # Exhaust rate limit for IP 1
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is True
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is True
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is False

    # Different IP should have its own limit
    assert check_rate_limit(key="ip:10.0.0.2", limit=2, window_seconds=300) is True


def test_bff_server_forwards_token_version():
    """BFF server should forward token_version in normalizeSessionUser.

    WEAKNESS, recorded here rather than fixed or silently accepted: this is still a
    source-token assertion. It is not the same defect as the tests removed above,
    because the token does occur in executable code (`spa-bff/src/server.ts` maps
    `token_version` and writes the `x-okr-token-version` header), so it is not
    certifying an inverted design. It nonetheless does not prove forwarding: deleting
    the header write while leaving the mapping, or the reverse, keeps it green. Real
    coverage would assert the outbound header on a state-changing route, which is what
    `spa-bff/test/forwarded_ip.test.ts` does for the client-IP header. Whether its own
    property is already covered behaviourally elsewhere was not established here.
    """
    source = _SERVER_TS.read_text(encoding="utf-8")
    assert "token_version" in source, (
        "normalizeSessionUser should include token_version"
    )
