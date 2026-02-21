from __future__ import annotations

import sys
from types import SimpleNamespace


def _fake_streamlit_with_secrets(monkeypatch, secrets: dict) -> None:
    monkeypatch.setitem(sys.modules, "streamlit", SimpleNamespace(secrets=secrets))


def test_runtime_config_reads_streamlit_secrets_when_env_missing(monkeypatch):
    from src.config_runtime import get_config_value

    monkeypatch.delenv("OKR_BACKEND_API_URL", raising=False)
    _fake_streamlit_with_secrets(
        monkeypatch,
        {"OKR_BACKEND_API_URL": "http://secret-api.local"},
    )

    assert get_config_value("OKR_BACKEND_API_URL", "") == "http://secret-api.local"


def test_runtime_config_env_precedence_over_streamlit_secrets(monkeypatch):
    from src.config_runtime import get_config_value

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://env-api.local")
    _fake_streamlit_with_secrets(
        monkeypatch,
        {"OKR_BACKEND_API_URL": "http://secret-api.local"},
    )

    assert get_config_value("OKR_BACKEND_API_URL", "") == "http://env-api.local"


def test_backend_client_uses_streamlit_secrets_for_backend_url(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.delenv("OKR_BACKEND_API_URL", raising=False)
    _fake_streamlit_with_secrets(
        monkeypatch,
        {"OKR_BACKEND_API_URL": "http://secret-api.local"},
    )

    assert backend_client.is_backend_enabled() is True
    assert backend_client._base_url() == "http://secret-api.local"


def test_crud_proxy_flag_respects_streamlit_secrets(monkeypatch):
    import src.crud as crud

    monkeypatch.delenv("OKR_BACKEND_PROXY_MUTATIONS", raising=False)
    _fake_streamlit_with_secrets(
        monkeypatch,
        {"OKR_BACKEND_PROXY_MUTATIONS": False},
    )
    monkeypatch.setattr("src.services.backend_client.is_backend_enabled", lambda: True)

    assert crud._backend_mutation_proxy_enabled() is False


def test_runtime_config_source_reports_env(monkeypatch):
    from src.config_runtime import get_config_value_with_source

    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")
    _fake_streamlit_with_secrets(
        monkeypatch,
        {"OKR_BACKEND_PROXY_MUTATIONS": False},
    )

    value, source = get_config_value_with_source("OKR_BACKEND_PROXY_MUTATIONS", "")
    assert value == "true"
    assert source == "env"


def test_runtime_config_source_reports_app_section(monkeypatch):
    from src.config_runtime import get_config_value_with_source

    monkeypatch.delenv("OKR_BACKEND_PROXY_MUTATIONS", raising=False)
    _fake_streamlit_with_secrets(
        monkeypatch,
        {"app": {"OKR_BACKEND_PROXY_MUTATIONS": "false"}},
    )

    value, source = get_config_value_with_source("OKR_BACKEND_PROXY_MUTATIONS", "")
    assert value == "false"
    assert source == "secrets_app"


def test_runtime_bool_config_with_source_honors_default(monkeypatch):
    from src.config_runtime import get_bool_config_with_source

    monkeypatch.delenv("OKR_BACKEND_PROXY_MUTATIONS", raising=False)
    _fake_streamlit_with_secrets(monkeypatch, {})

    value, source = get_bool_config_with_source("OKR_BACKEND_PROXY_MUTATIONS", True)
    assert value is True
    assert source == "default"
