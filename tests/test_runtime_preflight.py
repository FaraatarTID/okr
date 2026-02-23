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
    assert any(
        "External AI calls are disabled by policy" in msg for msg in report.infos
    )


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


def test_backend_proxy_missing_url_is_error_in_production():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="",
        runtime_env="production",
    )
    assert any("OKR_BACKEND_PROXY_MUTATIONS=true" in msg for msg in report.errors)


def test_backend_proxy_missing_url_is_warning_in_development():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="",
        runtime_env="development",
    )
    assert any("OKR_BACKEND_PROXY_MUTATIONS=true" in msg for msg in report.warnings)


def test_production_backend_requires_signing_secret():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="",
        runtime_env="production",
    )
    assert any("OKR_BACKEND_SIGNING_SECRET" in msg for msg in report.errors)


def test_production_disallows_local_backend_fallback():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        allow_local_backend_mutation_fallback=True,
        runtime_env="production",
    )
    assert any("OKR_ALLOW_LOCAL_MUTATION_FALLBACK" in msg for msg in report.errors)


def test_production_warns_when_proxy_reads_and_local_fallback_enabled():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_api_url="http://backend-api:8100",
        backend_proxy_reads=True,
        backend_service_token="token",
        backend_signing_secret="secret",
        allow_local_backend_read_fallback=True,
        runtime_env="production",
    )
    assert any("OKR_BACKEND_PROXY_READS=true" in msg for msg in report.warnings)


def test_legacy_global_fallback_maps_to_scoped_preflight_flags():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_api_url="http://backend-api:8100",
        backend_proxy_reads=True,
        backend_service_token="token",
        backend_signing_secret="secret",
        allow_local_backend_fallback=True,
        runtime_env="production",
    )
    assert any("OKR_ALLOW_LOCAL_MUTATION_FALLBACK" in msg for msg in report.errors)
    assert any("OKR_ALLOW_LOCAL_READ_FALLBACK=true" in msg for msg in report.warnings)


def test_production_requires_backend_proxy_mutations_enabled():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=False,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        runtime_env="production",
    )
    assert any("OKR_BACKEND_PROXY_MUTATIONS=true" in msg for msg in report.errors)


def test_production_requires_backend_api_url():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=False,
        backend_api_url="",
        runtime_env="production",
    )
    assert any("OKR_BACKEND_API_URL" in msg for msg in report.errors)


def test_production_requires_bootstrap_admin_password():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        bootstrap_admin_password="",
        runtime_env="production",
    )
    assert any("OKR_BOOTSTRAP_ADMIN_PASSWORD" in msg for msg in report.errors)


def test_production_requires_strong_bootstrap_admin_password():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        bootstrap_admin_password="weakpass",
        runtime_env="production",
    )
    assert any("at least 12 characters" in msg for msg in report.errors)


def test_production_requires_distributed_security_state_backend():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        bootstrap_admin_password="ValidAdmin123!",
        backend_security_state_backend="memory",
        runtime_env="production",
    )
    assert any("database or redis" in msg for msg in report.errors)


def test_production_accepts_database_security_state_backend():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        bootstrap_admin_password="ValidAdmin123!",
        backend_security_state_backend="database",
        runtime_env="production",
    )
    assert not any("database or redis" in msg for msg in report.errors)


def test_production_requires_redis_url_when_redis_backend_selected():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        bootstrap_admin_password="ValidAdmin123!",
        backend_security_state_backend="redis",
        backend_security_state_redis_url="",
        runtime_env="production",
    )
    assert any("OKR_BACKEND_SECURITY_STATE_REDIS_URL" in msg for msg in report.errors)


def test_production_accepts_redis_security_state_backend_with_url():
    report = evaluate_runtime_preflight(
        pdf_method="pdfshift",
        is_streamlit_cloud=False,
        has_pdfshift_key=True,
        gemini_api_key="valid-key",
        backend_proxy_mutations=True,
        backend_api_url="http://backend-api:8100",
        backend_service_token="token",
        backend_signing_secret="secret",
        bootstrap_admin_password="ValidAdmin123!",
        backend_security_state_backend="redis",
        backend_security_state_redis_url="redis://redis:6379/0",
        runtime_env="production",
    )
    assert not any(
        "OKR_BACKEND_SECURITY_STATE_REDIS_URL" in msg for msg in report.errors
    )
