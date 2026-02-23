# ruff: noqa: E402
"""Execution logic for backend async jobs."""

from __future__ import annotations

import base64
from typing import Any, Dict

from backend_app.path_setup import ensure_streamlit_app_on_path

ensure_streamlit_app_on_path()

from src.services.ai_provider import generate_json
from src.services.pdf_service import generate_pdf_bytes, generate_pdf_html


def _run_pdf_weekly_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    report_items = list(payload.get("report_items") or [])
    objective_stats = dict(payload.get("objective_stats") or {})
    total_time_str = str(payload.get("total_time_str") or "00:00")
    key_results = list(payload.get("key_results") or [])
    direction = str(payload.get("direction") or "LTR")
    title = str(payload.get("title") or "Work Report")
    time_label = str(payload.get("time_label") or "Last 7 Days")
    report_summary = payload.get("report_summary")
    achievements = payload.get("achievements")

    html = generate_pdf_html(
        report_items,
        objective_stats,
        total_time_str,
        key_results,
        direction=direction,
        title=title,
        time_label=time_label,
        report_summary=report_summary,
        achievements=achievements,
    )
    pdf_bytes = generate_pdf_bytes(html)
    if not pdf_bytes:
        raise RuntimeError("PDF generation failed.")

    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "content_b64": encoded,
        "content_type": "application/pdf",
        "filename": payload.get("filename") or "report.pdf",
    }


def _run_ai_generate_json_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Missing prompt for ai.generate_json job.")
    response = generate_json(prompt)
    if not isinstance(response, dict):
        raise RuntimeError("AI provider returned invalid payload.")
    return response


def run_job(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    job_kind = str(kind or "").strip().lower()
    if job_kind == "pdf.weekly":
        return _run_pdf_weekly_job(payload)
    if job_kind == "ai.generate_json":
        return _run_ai_generate_json_job(payload)
    raise ValueError(f"Unsupported job kind '{kind}'.")
