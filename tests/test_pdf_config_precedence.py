from __future__ import annotations


def test_pdfshift_api_key_env(monkeypatch):
    import src.services.pdf_service as pdf_service

    monkeypatch.setenv("PDFSHIFT_API_KEY", "env-key")

    assert pdf_service._resolve_pdfshift_api_key() == "env-key"


def test_pdf_method_env(monkeypatch):
    import src.services.pdf_service as pdf_service

    monkeypatch.setenv("PDF_METHOD", "pdfshift")
    monkeypatch.delenv("OKR_PDF_METHOD", raising=False)

    assert pdf_service.is_deployed_environment() is True


def test_pdf_method_supports_chromium_from_env(monkeypatch):
    import src.services.pdf_service as pdf_service

    monkeypatch.setenv("PDF_METHOD", "chromium")
    monkeypatch.delenv("OKR_PDF_METHOD", raising=False)

    assert pdf_service.get_pdf_method() == "chromium"
    assert pdf_service.is_deployed_environment() is True
