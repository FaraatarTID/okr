"""The Supabase REST transport must not echo its URL or key in the errors it raises.

`ai_service._fetch_node_for_analysis` puts the text of that error into a returned value that reaches a job's
`error_text`. httpx exception messages can include the request URL, so the transport rewraps them in fixed text;
these tests fail if a change starts passing the library message through.
"""

from __future__ import annotations

import httpx
import pytest

from _test_credentials import credential_password
from src.services import ai_service, supabase_api_mode_transport as transport

KEY = credential_password("rest_service_key", length=24)
QUERY = credential_password("rest_query_value", length=24)
USERINFO = credential_password("rest_userinfo", length=24)


class _FailingClient:
    def __init__(self, exc_factory):
        self._factory = exc_factory

    def request(self, method, url, **_kwargs):
        raise self._factory(f"{method} {url} refused")


@pytest.fixture
def rest_env(monkeypatch):
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    monkeypatch.setenv(
        "SUPABASE_URL", f"https://svc:{USERINFO}@db.example?token={QUERY}"
    )
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", KEY)


@pytest.mark.parametrize(
    "exc_type",
    [
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
        httpx.DecodingError,
    ],
)
def test_transport_errors_do_not_echo_url_or_key(monkeypatch, rest_env, exc_type):
    monkeypatch.setattr(
        transport,
        "_get_http_client",
        lambda: _FailingClient(lambda m: exc_type(f"{m} key={KEY}")),
    )

    with pytest.raises(transport.SupabaseTransportError) as caught:
        transport._rest_select("objective")

    text = str(caught.value)
    for secret in (KEY, QUERY, USERINFO):
        assert secret not in text
    assert "/rest/v1/objective" in text


def test_analysis_fallback_error_does_not_echo_credentials(monkeypatch, rest_env):
    monkeypatch.setattr(
        transport,
        "_get_http_client",
        lambda: _FailingClient(lambda m: httpx.ConnectError(f"{m} key={KEY}")),
    )
    import src.crud

    def _direct_fails(*_args, **_kwargs):
        raise RuntimeError("direct database unavailable")

    # `_fetch_node_for_analysis` does `from src.crud import get_node` inside the function, so patch the source.
    monkeypatch.setattr(src.crud, "get_node", _direct_fails)
    result = ai_service._fetch_node_for_analysis(1, "OBJECTIVE", "alice")

    # The REST fallback ran and failed (not the "not found" branch), so its error text is what is returned.
    assert "Node fetch failed (direct + REST)" in result["error"]
    text = str(result)
    for secret in (KEY, QUERY, USERINFO):
        assert secret not in text
