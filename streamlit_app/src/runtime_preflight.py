"""Runtime preflight policy checks for deployment safety."""

from dataclasses import dataclass, field
from typing import List, Optional


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
    has_pdfkit_module: bool,
    has_wkhtmltopdf: bool,
    gemini_api_key: Optional[str],
    external_ai_allowed: bool = True,
) -> RuntimePreflightReport:
    """Evaluate runtime safety constraints for PDF and AI integrations."""
    report = RuntimePreflightReport()
    method = _normalize_pdf_method(pdf_method)

    if method not in {"pdfshift", "pdfkit"}:
        report.errors.append(
            "Unsupported PDF_METHOD. Use one of: pdfshift, pdfkit."
        )
        return report

    if method == "pdfshift":
        if not has_pdfshift_key:
            report.errors.append(
                "PDF_METHOD=pdfshift but PDFShift API key is missing."
            )
        else:
            report.infos.append("PDF provider is PDFShift (cloud-safe mode).")

    if method == "pdfkit":
        if is_streamlit_cloud:
            report.errors.append(
                "Streamlit Cloud runtime detected with PDF_METHOD=pdfkit. "
                "Use PDF_METHOD=pdfshift for cloud deployments."
            )
        if not has_pdfkit_module:
            report.warnings.append(
                "pdfkit package is not installed; PDF export will fall back to HTML."
            )
        if not has_wkhtmltopdf:
            report.warnings.append(
                "wkhtmltopdf is not available; PDF export will fall back to HTML."
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
