from __future__ import annotations

from types import SimpleNamespace


def test_pdfshift_api_key_env_takes_precedence_over_secrets(monkeypatch):
    import src.services.pdf_service as pdf_service

    monkeypatch.setenv("PDFSHIFT_API_KEY", "env-key")
    monkeypatch.setattr(
        pdf_service,
        "st",
        SimpleNamespace(secrets={"pdfshift_api_key": "secret-key", "app": {}}),
    )
    monkeypatch.setattr(pdf_service, "_load_file_secrets", lambda: {})

    assert pdf_service._resolve_pdfshift_api_key() == "env-key"


def test_pdf_method_env_takes_precedence_over_secrets(monkeypatch):
    import src.services.pdf_service as pdf_service

    monkeypatch.setenv("PDF_METHOD", "pdfshift")
    monkeypatch.delenv("OKR_PDF_METHOD", raising=False)
    monkeypatch.setattr(
        pdf_service,
        "st",
        SimpleNamespace(secrets={"PDF_METHOD": "unsupported", "app": {}}),
    )
    monkeypatch.setattr(pdf_service, "_load_file_secrets", lambda: {})

    assert pdf_service.is_deployed_environment() is True


def test_pdf_method_falls_back_to_secrets_when_env_missing(monkeypatch):
    import src.services.pdf_service as pdf_service

    monkeypatch.delenv("PDF_METHOD", raising=False)
    monkeypatch.delenv("OKR_PDF_METHOD", raising=False)
    monkeypatch.setattr(
        pdf_service,
        "st",
        SimpleNamespace(secrets={"PDF_METHOD": "pdfshift", "app": {}}),
    )
    monkeypatch.setattr(pdf_service, "_load_file_secrets", lambda: {})

    assert pdf_service.is_deployed_environment() is True
