from __future__ import annotations


def test_runtime_config_source_reports_env(monkeypatch):
    from src.config_runtime import get_config_value_with_source

    monkeypatch.setenv("OKR_ENFORCE_STRONG_PASSWORD_POLICY", "true")

    value, source = get_config_value_with_source(
        "OKR_ENFORCE_STRONG_PASSWORD_POLICY", ""
    )
    assert value == "true"
    assert source == "env"


def test_runtime_bool_config_with_source_honors_default(monkeypatch):
    from src.config_runtime import get_bool_config_with_source

    monkeypatch.delenv("OKR_ENFORCE_STRONG_PASSWORD_POLICY", raising=False)

    value, source = get_bool_config_with_source(
        "OKR_ENFORCE_STRONG_PASSWORD_POLICY", True
    )
    assert value is True
    assert source == "default"
