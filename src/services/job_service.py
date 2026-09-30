"""High-level async job orchestration for UI flows."""

from __future__ import annotations

from typing import Any, Dict

from src.services.ai_provider import generate_json
from src.services.pdf_service import generate_pdf_bytes, generate_pdf_html


def _run_local(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = str(kind or "").strip().lower()
    if normalized == "ai.generate_json":
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return {"error": "Missing prompt."}
        return generate_json(prompt)

    if normalized == "pdf.weekly":
        html = generate_pdf_html(
            list(payload.get("report_items") or []),
            dict(payload.get("objective_stats") or {}),
            str(payload.get("total_time_str") or "00:00"),
            list(payload.get("key_results") or []),
            direction=str(payload.get("direction") or "LTR"),
            title=str(payload.get("title") or "Work Report"),
            time_label=str(payload.get("time_label") or "Last 7 Days"),
            report_summary=payload.get("report_summary"),
            achievements=payload.get("achievements"),
        )
        pdf_bytes = generate_pdf_bytes(html)
        if not pdf_bytes:
            return {"error": "PDF generation failed."}
        import base64

        return {
            "content_b64": base64.b64encode(pdf_bytes).decode("ascii"),
            "content_type": "application/pdf",
            "filename": str(payload.get("filename") or "report.pdf"),
        }

    return {"error": f"Unsupported job kind '{kind}'."}


def run_job_and_wait(
    *,
    kind: str,
    payload: Dict[str, Any],
    actor_username: str,
    timeout_seconds: int = 90,
    poll_seconds: float = 1.0,
) -> Dict[str, Any]:
    """Run a job in-process.

    ``actor_username``, ``timeout_seconds`` and ``poll_seconds`` are accepted
    for call-site compatibility; jobs execute synchronously in this process.
    """
    return _run_local(kind, payload)
