"""Runtime preflight helpers extracted from app.py."""

from __future__ import annotations

from typing import Any, Callable, Mapping


def get_pdf_method(
    *,
    cfg_value_fn: Callable[[str, str], str],
    has_pdfshift_api_key_fn: Callable[[], bool],
) -> str:
    method = (
        str(
            cfg_value_fn("PDF_METHOD", "")
            or cfg_value_fn("OKR_PDF_METHOD", "")
            or cfg_value_fn("pdf_method", "")
    )
        .strip()
        .lower()
    )
    if method == "shiftpdf":
        method = "pdfshift"
    if method in {"chrome", "playwright"}:
        method = "chromium"
    if method:
        return method
    if has_pdfshift_api_key_fn():
        return "pdfshift"
    return "pdfshift"


def is_streamlit_cloud_runtime(*, environ: Mapping[str, str]) -> bool:
    return bool(
        environ.get("STREAMLIT_SHARING_MODE") or environ.get("IS_STREAMLIT_CLOUD")
    )


def has_pdfshift_api_key(*, cfg_value_fn: Callable[[str, str], str]) -> bool:
    return bool(
        cfg_value_fn("PDFSHIFT_API_KEY", "").strip()
        or cfg_value_fn("pdfshift_api_key", "").strip()
    )


def has_chromium_runtime() -> bool:
    try:
        from src.services.pdf_service import is_chromium_runtime_available

        return bool(is_chromium_runtime_available())
    except Exception:
        return False


def runtime_preflight_strict_mode(*, cfg_value_fn: Callable[[str, str], str]) -> bool:
    # Security-first default: runtime preflight is strict unless explicitly disabled.
    raw = str(cfg_value_fn("OKR_STRICT_RUNTIME_PREFLIGHT", "")).strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return True


def env_bool_with_legacy(
    *,
    name: str,
    legacy_name: str,
    default: bool,
    cfg_value_fn: Callable[[str, str], str],
    env_bool_fn: Callable[[str, bool], bool],
) -> bool:
    raw = str(cfg_value_fn(name, "")).strip()
    if raw:
        return raw.lower() in {"1", "true", "yes", "on"}
    return env_bool_fn(legacy_name, default)


def run_pdf_preflight(
    *,
    st_module: Any,
    environ: Mapping[str, str],
    cfg_value_fn: Callable[[str, str], str],
    env_bool_fn: Callable[[str, bool], bool],
    get_config_value_with_source_fn: Callable[[str, str], tuple[str, str]],
    evaluate_runtime_preflight_fn: Callable[..., Any],
    get_api_key_fn: Callable[[], str | None],
    get_ai_provider_runtime_status_fn: Callable[[], Any],
    is_external_ai_allowed_fn: Callable[[], bool],
    get_pdf_method_fn: Callable[[], str],
    has_pdfshift_api_key_fn: Callable[[], bool],
    has_chromium_runtime_fn: Callable[[], bool],
    is_streamlit_cloud_runtime_fn: Callable[[], bool],
    runtime_preflight_strict_mode_fn: Callable[[], bool],
) -> None:
    if st_module.session_state.get("preflight_done"):
        return

    pdf_method = get_pdf_method_fn()
    has_pdfshift_key = has_pdfshift_api_key_fn()
    has_chromium_runtime = has_chromium_runtime_fn()
    is_cloud = is_streamlit_cloud_runtime_fn()
    ai_status = get_ai_provider_runtime_status_fn()

    backend_api_url, backend_api_url_source = get_config_value_with_source_fn(
        "OKR_BACKEND_API_URL", ""
    )
    
    # Legacy: We no longer allow opting out of proxy mutations if in a Streamlit context
    # backend_proxy_mutations = env_bool_fn("OKR_BACKEND_PROXY_MUTATIONS", True)
    
    # Backend segregation is strict: reads must use backend control plane.
    backend_proxy_reads = True

    report = evaluate_runtime_preflight_fn(
        pdf_method=pdf_method,
        is_streamlit_cloud=is_cloud,
        has_pdfshift_key=has_pdfshift_key,
        has_chromium_runtime=has_chromium_runtime,
        gemini_api_key=get_api_key_fn(),
        external_ai_allowed=is_external_ai_allowed_fn(),
        ai_provider=ai_status.provider,
        ai_provider_ready=ai_status.ready,
        ai_provider_message=ai_status.message,
        backend_api_url=backend_api_url,
        backend_proxy_mutations=True, # Strictly enforced
        backend_proxy_reads=backend_proxy_reads,
        allow_local_backend_mutation_fallback=False, # Strictly disabled
        allow_local_backend_read_fallback=False, # Strictly disabled
        backend_service_token=cfg_value_fn("OKR_BACKEND_SERVICE_TOKEN", ""),
        backend_signing_secret=cfg_value_fn("OKR_BACKEND_SIGNING_SECRET", ""),
        bootstrap_admin_password=str(environ.get("OKR_BOOTSTRAP_ADMIN_PASSWORD", "")),
        backend_security_state_backend=cfg_value_fn(
            "OKR_BACKEND_SECURITY_STATE_BACKEND",
            "memory",
        ),
        backend_security_state_redis_url=cfg_value_fn(
            "OKR_BACKEND_SECURITY_STATE_REDIS_URL",
            "",
        ),
        runtime_env=(
            cfg_value_fn("OKR_ENV", "")
            or cfg_value_fn("OKR_RUNTIME_ENV", "development")
        ),
    )
    for msg in report.errors:
        st_module.error(f"Runtime preflight: {msg}")
    for msg in report.warnings:
        st_module.warning(f"Runtime preflight: {msg}")


    st_module.session_state["preflight_done"] = True
    if report.errors and runtime_preflight_strict_mode_fn():
        st_module.stop()
