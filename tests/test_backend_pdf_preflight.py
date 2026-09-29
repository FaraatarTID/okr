"""The backend's startup preflight must judge the real PDF configuration.

`validate_runtime_preflight` used to pass `pdf_method="chromium"`, a pdfshift key and a
chromium runtime as constants, so its PDF half could not fail whatever was deployed. It now
reads the real values. A PDF renderer problem is advisory (logged), because the backend
serves everything else without one; every other finding still stops boot.
"""

from __future__ import annotations

import logging

import pytest

from backend_app import main_bootstrap_helpers as bootstrap
from src.runtime_preflight import is_pdf_finding
from src.services import pdf_service


@pytest.fixture()
def strict(monkeypatch):
    monkeypatch.setenv("OKR_STRICT_RUNTIME_PREFLIGHT", "true")
    monkeypatch.setenv("OKR_DEPLOYMENT_PROFILE", "")
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "database")


def _renderer(monkeypatch, *, method, key, chromium):
    monkeypatch.setattr(pdf_service, "get_pdf_method", lambda: method)
    monkeypatch.setattr(pdf_service, "has_pdfshift_api_key", lambda: key)
    monkeypatch.setattr(pdf_service, "is_chromium_runtime_available", lambda: chromium)


def test_chromium_without_a_runtime_is_reported_and_does_not_stop_boot(
    strict, monkeypatch, caplog
):
    _renderer(monkeypatch, method="chromium", key=False, chromium=False)

    with caplog.at_level(logging.WARNING, logger=bootstrap.__name__):
        bootstrap.validate_runtime_preflight()

    text = " ".join(r.getMessage() for r in caplog.records)
    assert "PDF_METHOD=chromium" in text and "unavailable" in text


def test_pdfshift_without_a_key_is_reported_and_does_not_stop_boot(
    strict, monkeypatch, caplog
):
    _renderer(monkeypatch, method="pdfshift", key=False, chromium=False)

    with caplog.at_level(logging.WARNING, logger=bootstrap.__name__):
        bootstrap.validate_runtime_preflight()

    assert any("PDF_METHOD=pdfshift" in r.getMessage() for r in caplog.records)


def test_a_working_renderer_logs_nothing(strict, monkeypatch, caplog):
    _renderer(monkeypatch, method="chromium", key=False, chromium=True)

    with caplog.at_level(logging.WARNING, logger=bootstrap.__name__):
        bootstrap.validate_runtime_preflight()

    assert not caplog.records


def test_an_unsupported_method_is_reported_not_swallowed_silently(
    strict, monkeypatch, caplog
):
    _renderer(monkeypatch, method="wkhtmltopdf", key=True, chromium=True)

    with caplog.at_level(logging.WARNING, logger=bootstrap.__name__):
        bootstrap.validate_runtime_preflight()

    assert any("Unsupported PDF_METHOD" in r.getMessage() for r in caplog.records)


def test_a_non_pdf_finding_still_stops_boot_alongside_a_pdf_one(
    strict, monkeypatch, caplog
):
    """The partition must not turn the whole check advisory."""
    _renderer(monkeypatch, method="chromium", key=False, chromium=False)
    monkeypatch.setenv("OKR_DEPLOYMENT_PROFILE", "single_tenant_saas")
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")

    with pytest.raises(RuntimeError) as exc:
        bootstrap.validate_runtime_preflight()

    assert "only OKR_DATA_ACCESS_MODE=database" in str(exc.value)
    assert "PDF_METHOD" not in str(exc.value)


def test_the_real_pdf_configuration_reaches_the_evaluation(strict, monkeypatch):
    seen = {}

    def _spy(**kwargs):
        seen.update(kwargs)
        from src.runtime_preflight import RuntimePreflightReport

        return RuntimePreflightReport()

    monkeypatch.setattr(bootstrap, "evaluate_runtime_preflight", _spy)
    _renderer(monkeypatch, method="pdfshift", key=True, chromium=False)

    bootstrap.validate_runtime_preflight()

    assert (
        seen["pdf_method"],
        seen["has_pdfshift_key"],
        seen["has_chromium_runtime"],
    ) == (
        "pdfshift",
        True,
        False,
    )


def test_non_strict_mode_still_skips_the_check(monkeypatch, caplog):
    monkeypatch.setenv("OKR_STRICT_RUNTIME_PREFLIGHT", "false")
    monkeypatch.setenv("OKR_DEPLOYMENT_PROFILE", "")
    _renderer(monkeypatch, method="chromium", key=False, chromium=False)

    with caplog.at_level(logging.WARNING, logger=bootstrap.__name__):
        bootstrap.validate_runtime_preflight()

    assert not caplog.records


def test_is_pdf_finding_matches_the_messages_the_evaluator_emits():
    """Keeps the prefix list honest: every PDF error the evaluator can raise is matched."""
    from src.runtime_preflight import evaluate_runtime_preflight

    def errors(method, key, runtime):
        return evaluate_runtime_preflight(
            pdf_method=method,
            has_pdfshift_key=key,
            has_chromium_runtime=runtime,
            backend_api_url="auto",
        ).errors

    # A healthy renderer leaves only non-PDF noise, so the difference is the PDF findings.
    assert errors("pdfshift", True, False) == []
    emitted = (
        errors("pdfshift", False, False)
        + errors("chromium", False, False)
        + errors("nonsense", False, False)
    )

    assert len(emitted) == 3, emitted
    assert all(is_pdf_finding(m) for m in emitted), emitted
    assert not is_pdf_finding("SaaS deployment profile permits only database")
    assert not is_pdf_finding(
        "OKR_BACKEND_API_URL is required for backend-owned mutations."
    )
