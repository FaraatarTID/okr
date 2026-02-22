"""Runtime preflight policy checks for deployment safety."""

from dataclasses import dataclass, field
from typing import List, Optional

from src.domain.password_policy import validate_password_policy


@dataclass
class RuntimePreflightReport:
    """Structured result for runtime configuration checks."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    infos: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _normalize_pdf_method(pdf_method: str) -> str:
    value = str(pdf_method or "").strip().lower()
    if value == "shiftpdf":
        value = "pdfshift"
    return value


def evaluate_runtime_preflight(
    *,
    pdf_method: str,
    is_streamlit_cloud: bool,
    has_pdfshift_key: bool,
    gemini_api_key: Optional[str],
    external_ai_allowed: bool = True,
    ai_provider: str = "gemini",
    ai_provider_ready: Optional[bool] = None,
    ai_provider_message: Optional[str] = None,
    backend_api_url: Optional[str] = None,
    backend_proxy_mutations: bool = False,
    backend_service_token: Optional[str] = None,
    backend_signing_secret: Optional[str] = None,
    bootstrap_admin_password: Optional[str] = None,
    allow_local_backend_fallback: bool = False,
    runtime_env: str = "development",
) -> RuntimePreflightReport:
    """Evaluate runtime safety constraints for PDF and AI integrations."""
    report = RuntimePreflightReport()
    method = _normalize_pdf_method(pdf_method)

    if method not in {"pdfshift"}:
        report.errors.append(
            "Unsupported PDF_METHOD. Use: pdfshift. Local pdfkit/wkhtmltopdf mode was removed for security hardening."
        )
        return report

    if not has_pdfshift_key:
        report.errors.append(
            "PDF_METHOD=pdfshift but PDFShift API key is missing."
        )
    else:
        report.infos.append("PDF provider is PDFShift (secure mode).")

    backend_url = str(backend_api_url or "").strip()
    env_name = str(runtime_env or "development").strip().lower()
    is_production = env_name in {"prod", "production"}

    if is_production and not backend_proxy_mutations:
        report.errors.append(
            "Production requires OKR_BACKEND_PROXY_MUTATIONS=true."
        )

    if is_production and not backend_url:
        report.errors.append(
            "Production requires OKR_BACKEND_API_URL for backend-owned mutations."
        )

    if backend_proxy_mutations and not backend_url:
        message = (
            "OKR_BACKEND_PROXY_MUTATIONS=true but OKR_BACKEND_API_URL is not set."
        )
        if is_production:
            report.errors.append(message)
        else:
            report.warnings.append(message)

    if backend_url and not str(backend_service_token or "").strip():
        message = (
            "OKR_BACKEND_API_URL is configured but OKR_BACKEND_SERVICE_TOKEN is missing."
        )
        if is_production:
            report.errors.append(message)
        else:
            report.warnings.append(message)

    if is_production and backend_url and not str(backend_signing_secret or "").strip():
        report.errors.append(
            "Production backend mode requires OKR_BACKEND_SIGNING_SECRET."
        )

    bootstrap_password = str(bootstrap_admin_password or "").strip()
    if is_production and not bootstrap_password:
        report.errors.append(
            "Production requires OKR_BOOTSTRAP_ADMIN_PASSWORD for secure admin bootstrap."
        )
    elif is_production:
        try:
            validate_password_policy(
                bootstrap_password,
                field_name="OKR_BOOTSTRAP_ADMIN_PASSWORD",
                strict=True,
            )
        except ValueError as exc:
            report.errors.append(str(exc))

    if is_production and allow_local_backend_fallback:
        report.errors.append(
            "OKR_ALLOW_LOCAL_BACKEND_FALLBACK should be disabled in production."
        )

    key = str(gemini_api_key or "").strip()
    if not external_ai_allowed:
        report.infos.append(
            "External AI calls are disabled by policy (ALLOW_EXTERNAL_AI=false)."
        )
        if key:
            report.infos.append(
                "Gemini API key is set but ignored while external AI is disabled."
            )
        return report

    provider = str(ai_provider or "gemini").strip().lower()
    if ai_provider_ready is False:
        report.warnings.append(
            ai_provider_message
            or f"AI provider '{provider}' is not fully configured; AI features will be disabled."
        )
        return report

    if ai_provider_message and ai_provider_ready is True:
        report.infos.append(ai_provider_message)

    if provider == "openai_compatible":
        report.infos.append("AI provider is openai_compatible.")
        return report

    if provider not in {"gemini", ""}:
        report.warnings.append(
            f"Unsupported AI provider '{provider}'; AI features may be unavailable."
        )
        return report

    if not key:
        report.warnings.append(
            "Gemini API key is not configured; AI features will be disabled."
        )
        return report

    low = key.lower()
    if any(
        token in low
        for token in ["your-api-key", "replace-me", "changeme", "<api-key>"]
    ):
        report.warnings.append(
            "Gemini API key looks like a placeholder; AI calls may fail."
        )

    return report
