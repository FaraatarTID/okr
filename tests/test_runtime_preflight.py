from src.runtime_preflight import evaluate_runtime_preflight


def test_pdfshift_requires_api_key():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=True,
        has_pdfshift_key=False,
        has_pdfkit_module=True,
        has_wkhtmltopdf=True,
        gemini_api_key="valid-key",
    )
    assert report.errors
    assert any("PDF_METHOD=pdfshift" in msg for msg in report.errors)


def test_streamlit_cloud_rejects_pdfkit_mode():
    report = evaluate_runtime_preflight(
        pdf_method="pdfkit",
        is_streamlit_cloud=True,
        has_pdfshift_key=True,
        has_pdfkit_module=True,
        has_wkhtmltopdf=True,
        gemini_api_key="valid-key",
    )
    assert report.errors
    assert any("Streamlit Cloud runtime detected" in msg for msg in report.errors)


def test_pdfkit_missing_local_dependencies_warns():
    report = evaluate_runtime_preflight(
        pdf_method="pdfkit",
        is_streamlit_cloud=False,
        has_pdfshift_key=False,
        has_pdfkit_module=False,
        has_wkhtmltopdf=False,
        gemini_api_key="valid-key",
    )
    assert not report.errors
    assert any("pdfkit package is not installed" in msg for msg in report.warnings)
    assert any("wkhtmltopdf is not available" in msg for msg in report.warnings)


def test_missing_or_placeholder_gemini_key_warns():
    missing = evaluate_runtime_preflight(
        pdf_method="pdfkit",
        is_streamlit_cloud=False,
        has_pdfshift_key=False,
        has_pdfkit_module=True,
        has_wkhtmltopdf=True,
        gemini_api_key=None,
    )
    assert any("Gemini API key is not configured" in msg for msg in missing.warnings)

    placeholder = evaluate_runtime_preflight(
        pdf_method="pdfkit",
        is_streamlit_cloud=False,
        has_pdfshift_key=False,
        has_pdfkit_module=True,
        has_wkhtmltopdf=True,
        gemini_api_key="your-api-key",
    )
    assert any("looks like a placeholder" in msg for msg in placeholder.warnings)


def test_valid_cloud_profile_is_clean():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=True,
        has_pdfshift_key=True,
        has_pdfkit_module=True,
        has_wkhtmltopdf=False,
        gemini_api_key="valid-key",
    )
    assert report.ok
