"""Rate-limit key isolation, and the record of the source-substring tests removed here.

Four source-substring tests have been removed from this file. The first three are
described first; the fourth, a token-version forwarding assertion, is recorded last.

Two asserted that `backend_app/security.py` mentions `x_forwarded_for` and
`forwarded`/`client_ip`; the third asserted that `spa-bff/src/proxy.ts` mentions
`x-forwarded-for`. After the behaviour they described was deliberately removed, all three
still passed - on comment text, since the comments explaining that those headers are NOT
read are what contained the strings. They therefore certified the inverse of the shipped
design, which is worse than certifying nothing.

A fourth, `test_bff_server_forwards_token_version`, asserted only that
`spa-bff/src/server.ts` contains the string `token_version`. It was the weaker case: the
token does occur in executable code, so it did not certify an inverted design. It still
did not prove forwarding, though - deleting the header write while keeping the mapping, or
the reverse, left it green. Its own docstring asked whether the property it named was
already covered behaviourally elsewhere; that question is now answered, and it is. Each of
these was read and confirmed before the assertion was deleted, not assumed:

- `spa-bff/test/token_version.test.ts:36-73` asserts the outbound
  `x-okr-token-version` header equals the session's version on a proxied POST;
- `:75-110` asserts the header is absent when the session carries no version;
- `:112-146` asserts the login response preserves the value that `server.ts` maps, and
  `:148-182` covers the missing-field case.

So the mapping and the header write are both pinned by behaviour, and the substring
assertion added nothing a behavioural test did not already cover.

The remaining intended properties are covered behaviourally:
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

The one test kept below is not a substring check of that kind: it exercises the limiter's
keying directly, so it asserts the behaviour rather than the presence of a symbol.
"""

from backend_app.rate_limiter import check_rate_limit


def test_rate_limit_uses_forwarded_ip_for_isolation():
    """Different keys get independent rate limits."""
    # Exhaust rate limit for IP 1
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is True
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is True
    assert check_rate_limit(key="ip:10.0.0.1", limit=2, window_seconds=300) is False

    # Different IP should have its own limit
    assert check_rate_limit(key="ip:10.0.0.2", limit=2, window_seconds=300) is True
