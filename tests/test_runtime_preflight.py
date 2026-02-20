from src.runtime_preflight import evaluate_runtime_preflight


def test_pdfshift_requires_api_key():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=True,
        has_pdfshift_key=False,
        gemini_api_key="valid-key",
    )
    assert report.errors
    assert any("PDF_METHOD=pdfshift" in msg for msg in report.errors)


def test_pdfkit_mode_is_rejected_in_secure_runtime():
    report = evaluate_runtime_preflight(
        pdf_method="pdfkit",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
    )
    assert report.errors
    assert any("removed for security hardening" in msg for msg in report.errors)


def test_missing_or_placeholder_gemini_key_warns():
    missing = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key=None,
        external_ai_allowed=True,
    )
    assert any("Gemini API key is not configured" in msg for msg in missing.warnings)

    placeholder = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="your-api-key",
        external_ai_allowed=True,
    )
    assert any("looks like a placeholder" in msg for msg in placeholder.warnings)


def test_valid_cloud_profile_is_clean():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=True,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
    )
    assert report.ok


def test_external_ai_policy_disables_key_requirement():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key=None,
        external_ai_allowed=False,
    )
    assert not any("Gemini API key is not configured" in msg for msg in report.warnings)
    assert any("External AI calls are disabled by policy" in msg for msg in report.infos)


def test_openai_compatible_provider_does_not_require_gemini_key():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key=None,
        external_ai_allowed=True,
        ai_provider="openai_compatible",
        ai_provider_ready=True,
        ai_provider_message="AI provider 'openai_compatible' is configured.",
    )
    assert not any("Gemini API key is not configured" in msg for msg in report.warnings)
    assert any("AI provider is openai_compatible." in msg for msg in report.infos)


def test_provider_not_ready_warns():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key=None,
        external_ai_allowed=True,
        ai_provider="openai_compatible",
        ai_provider_ready=False,
        ai_provider_message="AI provider 'openai_compatible' missing required config: AI_BASE_URL, AI_MODEL.",
    )
    assert any("missing required config" in msg for msg in report.warnings)
