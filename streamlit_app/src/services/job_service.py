"""High-level async job orchestration for Streamlit UI flows."""

from __future__ import annotations

import time
from typing import Any, Dict

from src.services.backend_client import (
    get_job,
    is_backend_enabled,
    submit_job,
)
from src.services.ai_provider import generate_json
from src.services.pdf_service import generate_pdf_html, generate_pdf_with_pdfshift_bytes


def _is_transient_backend_error(payload: Dict[str, Any]) -> bool:
    try:
        code = int(payload.get("status_code") or 0)
    except Exception:
        code = 0
    if code == 0 or code in {500, 502, 503, 504}:
        return True
    message = str(payload.get("error") or "").strip().lower()
    return any(
        token in message
        for token in {
            "connection",
            "timed out",
            "timeout",
            "temporar",
        }
    )


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
        pdf_bytes = generate_pdf_with_pdfshift_bytes(html)
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
    if not is_backend_enabled():
        return _run_local(kind, payload)

    submitted = submit_job(
        kind=kind,
        payload=payload,
        actor_username=actor_username,
        max_attempts=2,
    )
    if "error" in submitted:
        if _is_transient_backend_error(submitted):
            return _run_local(kind, payload)
        return {"error": submitted["error"]}

    job_id = str(submitted.get("id") or "").strip()
    if not job_id:
        return {"error": "Backend returned invalid job id."}

    started = time.time()
    while time.time() - started <= float(timeout_seconds):
        state = get_job(job_id, actor_username)
        if "error" in state:
            if _is_transient_backend_error(state):
                return _run_local(kind, payload)
            return {"error": state["error"]}
        status_value = str(state.get("status") or "").strip().lower()
        if status_value == "succeeded":
            return dict(state.get("result") or {})
        if status_value in {"failed", "cancelled"}:
            return {"error": state.get("error_text") or f"Job {status_value}."}
        time.sleep(max(0.2, float(poll_seconds)))
    return _run_local(kind, payload)
