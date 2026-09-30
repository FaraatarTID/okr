"""The removed ``supabase_api`` data-access mode must fail loudly, never silently."""

from __future__ import annotations

import pytest

from backend_app.main_bootstrap_helpers import validate_runtime_preflight
from src.runtime_preflight import evaluate_runtime_preflight


def _report(mode: str, profile: str = ""):
    return evaluate_runtime_preflight(
        pdf_method="chromium",
        has_pdfshift_key=False,
        has_chromium_runtime=True,
        external_ai_allowed=False,
        backend_api_url="auto",
        deployment_profile=profile,
        data_access_mode=mode,
    )


@pytest.mark.parametrize("profile", ["", "on_premise", "single_tenant_saas"])
def test_preflight_rejects_supabase_api_in_every_profile(profile):
    report = _report("supabase_api", profile)

    assert any("supabase_api" in error for error in report.errors)
    assert any("OKR_DATA_ACCESS_MODE=database" in error for error in report.errors)


def test_preflight_accepts_database_mode():
    assert not [e for e in _report("database").errors if "DATA_ACCESS_MODE" in e]


@pytest.mark.parametrize("strict", ["true", "false"])
def test_backend_startup_refuses_supabase_api_even_when_preflight_is_relaxed(
    monkeypatch, strict
):
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    monkeypatch.setenv("OKR_STRICT_RUNTIME_PREFLIGHT", strict)
    monkeypatch.delenv("OKR_DEPLOYMENT_PROFILE", raising=False)

    with pytest.raises(RuntimeError, match="supabase_api"):
        validate_runtime_preflight()
