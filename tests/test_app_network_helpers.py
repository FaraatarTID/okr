from __future__ import annotations

from types import SimpleNamespace

from src.ui import app_network_helpers


def _st_with_headers(headers):
    return SimpleNamespace(context=SimpleNamespace(headers=headers))


def test_get_client_ip_prefers_x_forwarded_for_first_hop():
    st_module = _st_with_headers(
        {"X-Forwarded-For": "203.0.113.7, 198.51.100.5", "X-Real-IP": "198.51.100.9"}
    )

    client_ip = app_network_helpers.get_client_ip_from_streamlit(st_module=st_module)

    assert client_ip == "203.0.113.7"


def test_get_client_ip_falls_back_to_x_real_ip():
    st_module = _st_with_headers({"X-Real-IP": "198.51.100.9"})

    client_ip = app_network_helpers.get_client_ip_from_streamlit(st_module=st_module)

    assert client_ip == "198.51.100.9"


def test_get_client_ip_returns_none_without_headers():
    st_module = SimpleNamespace(context=SimpleNamespace(headers=None))

    client_ip = app_network_helpers.get_client_ip_from_streamlit(st_module=st_module)

    assert client_ip is None


def test_get_client_ip_returns_none_on_header_parse_error():
    class _BrokenHeaders:
        def items(self):
            raise RuntimeError("boom")

    st_module = _st_with_headers(_BrokenHeaders())

    client_ip = app_network_helpers.get_client_ip_from_streamlit(st_module=st_module)

    assert client_ip is None
