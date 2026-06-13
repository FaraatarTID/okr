from __future__ import annotations

import sys
from types import SimpleNamespace


def test_runtime_config_source_reports_env(monkeypatch):
    from src.config_runtime import get_config_value_with_source

    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")

    value, source = get_config_value_with_source("OKR_BACKEND_PROXY_MUTATIONS", "")
    assert value == "true"
    assert source == "env"


def test_runtime_bool_config_with_source_honors_default(monkeypatch):
    from src.config_runtime import get_bool_config_with_source

    monkeypatch.delenv("OKR_BACKEND_PROXY_MUTATIONS", raising=False)

    value, source = get_bool_config_with_source("OKR_BACKEND_PROXY_MUTATIONS", True)
    assert value is True
    assert source == "default"
