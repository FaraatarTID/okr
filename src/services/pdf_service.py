"""
Unified PDF generator in secure mode.
Supported binary renderers:
- PDFShift API (`PDF_METHOD=pdfshift`)
- Chromium via Playwright (`PDF_METHOD=chromium`)
"""

from __future__ import annotations

import os
import platform
import datetime
import base64
import logging
from html import escape as html_escape
from io import BytesIO
from src.services.http_client import post_json_with_retry

# Try importing optional PDFShift dependency.
PDFSHIFT_AVAILABLE = False

try:
    import requests  # type: ignore[import]

    PDFSHIFT_AVAILABLE = True
except ImportError:
    requests = None

# Optional Chromium renderer dependency.
PLAYWRIGHT_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None


_PDF_METHOD_ALIASES = {
    "shiftpdf": "pdfshift",
    "chrome": "chromium",
    "playwright": "chromium",
}
_SUPPORTED_PDF_METHODS = {"pdfshift", "chromium"}
_LOGGER = logging.getLogger(__name__)


def _escape(value):
    if value is None:
        return ""
    return html_escape(str(value), quote=True)


def _get_env(name: str, default: str = "") -> str:
    """Read a config value from environment variables only."""
    return str(os.getenv(name, default)).strip()


def _get_secret_value(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _resolve_pdfshift_api_key() -> str:
    env_key = str(os.getenv("PDFSHIFT_API_KEY", "")).strip()
    if env_key:
        return env_key

    key = _get_secret_value(
        "pdfshift_api_key",
        "PDFSHIFT_API_KEY",
    )
    if key:
        return key
    return ""


def _resolve_pdf_method() -> str:
    method = (
        str(os.getenv("PDF_METHOD", os.getenv("OKR_PDF_METHOD", ""))).strip().lower()
    )
    if method:
        return _PDF_METHOD_ALIASES.get(method, method)

    method = _get_secret_value("PDF_METHOD", "pdf_method").lower()
    if method:
        return _PDF_METHOD_ALIASES.get(method, method)

    return "pdfshift"


def _resolve_chromium_executable_path() -> str:
    value = str(
        os.getenv(
            "OKR_CHROMIUM_EXECUTABLE_PATH",
            os.getenv("CHROMIUM_EXECUTABLE_PATH", ""),
        )
    ).strip()
    if value:
        return value
    secret_value = _get_secret_value(
        "OKR_CHROMIUM_EXECUTABLE_PATH",
        "CHROMIUM_EXECUTABLE_PATH",
        "chromium_executable_path",
    )
    if secret_value:
        return secret_value

    # Best-effort auto-detection for managed Linux runtimes.
    for candidate in (
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ):
        if os.path.exists(candidate):
            return candidate
    return ""


def get_pdf_method() -> str:
    return _resolve_pdf_method()


def is_chromium_runtime_available() -> bool:
    return bool(PLAYWRIGHT_AVAILABLE)


def is_deployed_environment():
    """
    Resolve whether PDF binary generation is enabled in secure mode.
    Returns True when PDF_METHOD resolves to a supported secure renderer.
    """
    return _resolve_pdf_method() in _SUPPORTED_PDF_METHODS


def get_base64_font(font_path):
    """Helper function to convert font file to base64 for embedding"""
    try:
        if os.path.exists(font_path):
            with open(font_path, "rb") as font_file:
                return base64.b64encode(font_file.read()).decode("utf-8")
    except Exception as e:
        _LOGGER.warning("Font error: %s", e)
    return ""


def generate_pdf_html(
    report_items,
    objective_stats,
    total_time_str,
    key_results,
    direction="RTL",
    title="Weekly Work Report",
    time_label="Last 7 Days",
    report_summary=None,
    achievements=None,
):
    """
    Generate HTML content for PDF (common for both methods)
    """
    align = "right" if direction.upper() == "RTL" else "left"
    dir_attr = _escape(direction.lower())

    # Find font path
    font_path = None
    possible_paths = [
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets",
            "fonts",
            "Vazirmatn-Regular.ttf",
        ),
        os.path.join(
            os.path.dirname(__file__), "assets", "fonts", "Vazirmatn-Regular.ttf"
        ),
        "assets/fonts/Vazirmatn-Regular.ttf",
        "./Vazirmatn-Regular.ttf",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            font_path = path
            break

    font_base64 = get_base64_font(font_path) if font_path else ""

    html = f"""
<!DOCTYPE html>
<html dir="{dir_attr}">
<head>
    <meta charset="UTF-8">
    <style>
        @font-face {{
            font-family: 'Vazirmatn';
            src: url('data:font/ttf;base64,{font_base64}') format('truetype');
        }}
        body {{
            font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif;
            font-size: 13px;
            color: #333;
            direction: {dir_attr};
            text-align: {align};
            padding: 1.5cm;
            line-height: 1.4;
        }}
        h1 {{ color: #2c3e50; font-size: 24px; margin-bottom: 5px; border-bottom: 3px solid #3498db; padding-bottom: 10px; display: inline-block; }}
        h2 {{ color: #34495e; font-size: 18px; margin-top: 25px; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        h3 {{ color: #7f8c8d; font-size: 16px; margin-top: 20px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        /* Modern Table Styling */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #f8f9fa;
            color: #2c3e50;
            border-bottom: 2px solid #dde2e6;
            padding: 12px 10px;
            font-weight: 600;
            font-size: 12px;
            text-align: {align};
            white-space: nowrap;
        }}
        td {{
            border-bottom: 1px solid #eee;
            padding: 10px 10px;
            vertical-align: top;
            text-align: {align};
        }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        tr:hover {{ background-color: #f1f1f1; }}
        tr {{ page-break-inside: avoid; }}

        /* KPI Cards */
        .total-box {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 16px;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: inline-block;
        }}

        /* Status Badges */
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .badge-green {{ background-color: #e8f5e9; color: #2e7d32; }} /* On Track */
        .badge-amber {{ background-color: #fff8e1; color: #f57f17; }} /* At Risk */
        .badge-red {{ background-color: #ffebee; color: #c62828; }}   /* Overdue */
        .badge-gray {{ background-color: #f5f5f5; color: #616161; }}  /* None */

        .text-muted {{ color: #7f8c8d; font-size: 11px; }}
        
        /* Executive Summary Card */
        .exec-summary {{
            background-color: #fff;
            border: 1px solid #e0e0e0;
            border-left: 5px solid #2ecc71;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}

        .page-break {{ page-break-after: always; }}
    </style>
</head>
<body>
    <div id="header">
        <h1 style="border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">{_escape(title)}</h1>
        <p>Generated: {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC</p>
    </div>

    <div class="total-box">
        Total Time ({_escape(time_label)}): {_escape(total_time_str)}
    </div>

"""
    # Executive Summary Section
    if report_summary:
        # Treat summary text as untrusted input and render as escaped plain text.
        summary_text = str(report_summary.get("summary_markdown", "") or "")
        summary_html = _escape(summary_text).replace("\n", "<br>")
        highlights = report_summary.get("highlights", [])

        html += f"""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #2ecc71;">
        <h2 style="margin-top: 0;">Executive Summary</h2>
        <div style="font-size: 14px; line-height: 1.6;">{summary_html}</div>
"""
        if highlights:
            html += """
        <ul style="margin-top: 15px;">
"""
            for h in highlights:
                html += f"""            <li style="margin-bottom: 5px; font-weight: 500;">{_escape(h)}</li>"""
            html += """
        </ul>
"""
        html += """
    </div>
"""

    # Achievements Section
    if achievements:
        html += """
    <div style="margin-bottom: 20px;">
        <h3>Key Achievements</h3>
        <ul style="list-style-type: none; padding: 0;">
"""
        for a in achievements:
            html += f"""
            <li style="padding: 10px; border-bottom: 1px solid #eee; display: flex; align-items: center;">
                <span style="color: #2ecc71; margin-right: 10px; font-size: 1.2em;">[OK]</span>
                <span style="font-weight: 500;">{_escape(a)}</span>
            </li>"""
        html += """
        </ul>
    </div>
"""

    html += """
    <h3>Work Log</h3>
"""

    # Table of Tasks
    if report_items:
        html += """
    <table>
        <thead>
            <tr>
                <th>Task</th>
                <th style="width: 15%;">Objective</th>
                <th style="width: 15%;">Key Result</th>
                <th style="width: 100px;">Date/Time</th>
                <th style="width: 60px;">Dur</th>
                <th style="width: 80px;">Deadline</th>
                <th style="width: 25%;">Summary</th>
            </tr>
        </thead>
        <tbody>
"""
        for item in report_items:
            task_name = _escape(item.get("Task", "Untitled"))
            date_str = _escape(item.get("Date", ""))
            time_str = _escape(item.get("Time", ""))
            duration = item.get("Duration (m)", 0)
            summary = _escape(item.get("Summary", ""))
            obj_title = _escape(item.get("Objective", "-"))
            kr_title = _escape(item.get("KeyResult", "-"))
            deadline = _escape(item.get("Deadline", "-"))

            # Format Date/Time
            date_time_html = f"""
                <div style="font-weight:bold;">{date_str}</div>
                <div class="text-muted">{time_str}</div>
            """

            # Format Deadline Badge
            badge_class = "badge-gray"
            if "On Track" in deadline:
                badge_class = "badge-green"
            elif "At Risk" in deadline:
                badge_class = "badge-amber"
            elif "Overdue" in deadline:
                badge_class = "badge-red"

            deadline_html = (
                f'<span class="badge {badge_class}">{deadline}</span>'
                if deadline != "-"
                else "-"
            )

            html += f"""
            <tr>
                <td><strong>{task_name}</strong></td>
                <td>{obj_title}</td>
                <td>{kr_title}</td>
                <td>{date_time_html}</td>
                <td>{_escape(duration)}m</td>
                <td>{deadline_html}</td>
                <td style="color: #555;">{summary}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>
"""
    else:
        html += """
    <p>No work recorded in the this period.</p>
"""

    # Objective Stats
    html += """
    <h3>Time Distribution by Objective</h3>
"""

    if objective_stats:
        sorted_stats = sorted(
            objective_stats.items(), key=lambda item: item[1], reverse=True
        )
        total_mins = sum(v for k, v in objective_stats.items())

        def fmt(m):
            h = int(m // 60)
            mn = int(m % 60)
            if h > 0:
                return f"{h}h {mn}m"
            return f"{mn}m"

        html += """
    <table>
        <thead>
            <tr>
                <th>Objective</th>
                <th style="width: 100px;">Time</th>
                <th style="width: 80px;">%</th>
            </tr>
        </thead>
        <tbody>
"""

        for obj_title, mins in sorted_stats:
            pct = (mins / total_mins * 100) if total_mins > 0 else 0

            html += f"""
            <tr>
                <td>{_escape(obj_title)}</td>
                <td>{_escape(fmt(mins))}</td>
                <td>{pct:.1f}%</td>
            </tr>
"""
        html += """
        </tbody>
    </table>
"""
    else:
        html += """
    <p>No objective data.</p>
"""

    # Key Result Strategic Status
    if key_results:
        html += """
    <h3>Key Result Strategic Status</h3>
    <table>
        <thead>
            <tr>
                <th>Key Result</th>
                <th style="width: 50px;">Prog</th>
                <th style="width: 50px;">Eff</th>
                <th style="width: 50px;">Qual</th>
                <th style="width: 50px;">Full</th>
            </tr>
        </thead>
        <tbody>
"""

        for kr in key_results:
            kr_title = _escape(kr.get("title", "Untitled"))
            progress = kr.get("progress", 0)

            an = kr.get("aiAnalysis")
            eff_score = "N/A"
            qual_score = "N/A"
            fulfillment = "N/A"

            analysis_html = ""

            if an and isinstance(an, dict):
                e_val = an.get("efficiency_score")
                q_val = an.get("effectiveness_score")
                o_val = an.get("overall_score")

                if e_val is not None:
                    eff_score = f"{e_val}%"
                if q_val is not None:
                    qual_score = f"{q_val}%"
                if o_val is not None:
                    fulfillment = f"{o_val}%"

                summary = _escape(an.get("summary", ""))
                gap = _escape(an.get("gap_analysis", ""))
                quality = _escape(an.get("quality_assessment", ""))

                if summary or gap or quality:
                    analysis_html = f"""
                    <tr>
                        <td colspan="5" style="background-color: #fcfcfc; padding: 10px 15px; border-top: none;">
                            <div style="font-size: 11px; color: #555;">
                                {f"<p><strong>Summary:</strong> {summary}</p>" if summary else ""}
                                {f"<p><strong>Gap Analysis:</strong> {gap}</p>" if gap else ""}
                                {f"<p><strong>Quality Assessment:</strong> {quality}</p>" if quality else ""}
                            </div>
                        </td>
                    </tr>
"""

            html += f"""
            <tr style="border-bottom: {"none" if analysis_html else "1px solid #dee2e6"};">
                <td>{kr_title}</td>
                <td>{_escape(progress)}%</td>
                <td>{_escape(eff_score)}</td>
                <td>{_escape(qual_score)}</td>
                <td>{_escape(fulfillment)}</td>
            </tr>
            {analysis_html}
"""
        html += """
        </tbody>
    </table>
"""

    html += """
</body>
</html>
"""
    return html


def generate_pdf_with_pdfshift(html):
    """
    Generate PDF using PDFShift API (secure mode).
    """
    pdf_bytes = generate_pdf_with_pdfshift_bytes(html)
    if pdf_bytes is None:
        _LOGGER.error("PDFShift failed. PDF export is unavailable.")
        return None
    return BytesIO(pdf_bytes)


def generate_pdf_with_pdfshift_bytes(html, *, api_key: str = ""):
    """
    Backend-safe PDFShift execution that returns raw PDF bytes.
    """
    try:
        pdfshift_api_key = str(api_key or "").strip() or _resolve_pdfshift_api_key()
        if not pdfshift_api_key:
            return None

        response = post_json_with_retry(
            "https://api.pdfshift.io/v3/convert/pdf",
            headers={"X-API-Key": pdfshift_api_key},
            json_payload={
                "source": html,
                "sandbox": True,
                "landscape": True,
                "format": "A4",
                "use_print": False,
            },
            timeout=(5.0, 60.0),
            retries=2,
        )

        if response.status_code == 200:
            return response.content
        _LOGGER.warning("PDFShift API Error: %s", response.status_code)
        return None

    except Exception as e:
        _LOGGER.warning("PDFShift Exception: %s: %s", type(e).__name__, str(e)[:200])
        return None


def generate_pdf_with_chromium(html):
    """
    Generate PDF using Chromium/Playwright (secure local renderer mode).
    """
    pdf_bytes = generate_pdf_with_chromium_bytes(html)
    if pdf_bytes is None:
        _LOGGER.error("Chromium PDF rendering failed. PDF export is unavailable.")
        return None
    return BytesIO(pdf_bytes)


def generate_pdf_with_chromium_bytes(html, *, executable_path: str = ""):
    """
    Backend-safe Chromium execution that returns raw PDF bytes.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    browser = None
    context = None
    try:
        resolved_executable = (
            str(executable_path or "").strip()
            or str(_resolve_chromium_executable_path() or "").strip()
        )
        launch_kwargs: dict[str, object] = {"headless": True}
        if resolved_executable:
            launch_kwargs["executable_path"] = resolved_executable

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context()
            page = context.new_page()
            page.set_content(str(html or ""), wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                landscape=True,
                print_background=True,
                prefer_css_page_size=True,
            )
            return pdf_bytes
    except Exception as exc:
        _LOGGER.warning("Chromium PDF Exception: %s", exc)
        return None
    finally:
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass


def generate_pdf_bytes(html, *, method: str = ""):
    """
    Generate PDF bytes using configured or explicitly supplied method.
    """
    resolved = str(method or "").strip().lower() or _resolve_pdf_method()
    resolved = _PDF_METHOD_ALIASES.get(resolved, resolved)
    if resolved == "pdfshift":
        return generate_pdf_with_pdfshift_bytes(html)
    if resolved == "chromium":
        return generate_pdf_with_chromium_bytes(html)
    return None


def generate_weekly_pdf_v2(
    report_items,
    objective_stats,
    total_time_str,
    key_results,
    direction="RTL",
    title="Weekly Work Report",
    time_label="Last 7 Days",
    report_summary=None,
    achievements=None,
):
    """
    Main PDF generation function.

    Returns: BytesIO object containing the PDF data, or None if generation fails
    """

    method = _resolve_pdf_method()
    is_deployed = method in _SUPPORTED_PDF_METHODS

    # Generate HTML (common for both methods)
    html = generate_pdf_html(
        report_items,
        objective_stats,
        total_time_str,
        key_results,
        direction,
        title,
        time_label,
        report_summary,
        achievements,
    )

    if not is_deployed:
        _LOGGER.error("Unsupported PDF_METHOD. Use one of: pdfshift, chromium.")
        return None

    pdf_bytes = generate_pdf_bytes(html, method=method)
    if not pdf_bytes:
        if method == "pdfshift":
            _LOGGER.error("PDFShift PDF rendering failed. Check API key/connectivity.")
        elif method == "chromium":
            _LOGGER.error(
                "Chromium PDF rendering failed. Install Playwright and Chromium browser."
            )
        else:
            _LOGGER.error("PDF rendering failed.")
        return None
    return BytesIO(pdf_bytes)


def get_pdf_generator_info():
    """
    Return information about the current PDF generation setup
    """
    method = _resolve_pdf_method()
    is_deployed = method in _SUPPORTED_PDF_METHODS

    info = {
        "environment": "Secure mode" if is_deployed else "Unsupported PDF method",
        "method": method,
        "pdfshift_available": PDFSHIFT_AVAILABLE,
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "platform": platform.system(),
    }

    return info


def has_pdfshift_api_key() -> bool:
    """Return True when a non-empty PDFShift API key is configured."""
    return bool(str(_resolve_pdfshift_api_key() or "").strip())


def get_chromium_executable_path() -> str:
    """Return configured or auto-detected Chromium executable path."""
    return str(_resolve_chromium_executable_path() or "").strip()


def get_pdf_runtime_diagnostics() -> dict[str, object]:
    """Return non-sensitive PDF runtime diagnostics for admin health panels."""
    info = get_pdf_generator_info()
    method = str(info.get("method") or "").strip().lower()
    chromium_path = get_chromium_executable_path()

    return {
        **info,
        "supported_method": method in _SUPPORTED_PDF_METHODS,
        "pdfshift_api_key_configured": has_pdfshift_api_key(),
        "chromium_executable_path": chromium_path,
        "chromium_executable_detected": bool(chromium_path),
        "managed_cloud_runtime": bool(
            os.getenv("OKR_MANAGED_CLOUD") or os.getenv("IS_CLOUD_RUNTIME")
        ),
    }


def generate_achievement_portfolio_pdf(portfolio: dict, direction: str = "RTL"):
    """
    Generate a professional Achievement Portfolio PDF.

    Args:
        portfolio: Dict from reporting.generate_achievement_portfolio()
        direction: 'RTL' or 'LTR'

    Returns: BytesIO object containing the PDF, or None on failure.
    """
    _ALLOWED_DIR = {"ltr", "rtl", "LTR", "RTL"}
    if direction not in _ALLOWED_DIR:
        direction = "RTL"
    align = "right" if direction.upper() == "RTL" else "left"
    dir_attr = _escape(direction.lower())

    user_name = _escape(portfolio.get("user", "Team Member"))
    generated_at = _escape(portfolio.get("generated_at", ""))
    summary = _escape(portfolio.get("summary_text", ""))
    total_achievements = portfolio.get("total_achievements", 0)
    total_hours = portfolio.get("total_high_impact_hours", 0)

    # Font embedding
    font_path = None
    possible_paths = [
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets",
            "fonts",
            "Vazirmatn-Regular.ttf",
        ),
        os.path.join(
            os.path.dirname(__file__), "assets", "fonts", "Vazirmatn-Regular.ttf"
        ),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            font_path = path
            break
    font_base64 = get_base64_font(font_path) if font_path else ""

    html = f"""
<!DOCTYPE html>
<html dir="{dir_attr}">
<head>
    <meta charset="UTF-8">
    <style>
        @font-face {{
            font-family: 'Vazirmatn';
            src: url('data:font/ttf;base64,{font_base64}') format('truetype');
        }}
        body {{
            font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif;
            font-size: 13px; color: #333; direction: {dir_attr};
            text-align: {align}; padding: 1.5cm; line-height: 1.5;
        }}
        h1 {{ color: #1f2933; font-size: 22px; border-bottom: 3px solid #0f766e; padding-bottom: 8px; }}
        h2 {{ color: #34495e; font-size: 16px; margin-top: 24px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th {{ background: #f0f7f5; color: #1f2933; padding: 10px 8px; border-bottom: 2px solid #d2d2d2; text-align: {align}; font-size: 11px; }}
        td {{ padding: 8px; border-bottom: 1px solid #eee; text-align: {align}; }}
        tr:nth-child(even) {{ background: #fafafa; }}
        .summary-box {{ background: linear-gradient(135deg, #0f766e, #12a39a); color: #fff; padding: 16px 20px; border-radius: 10px; margin: 16px 0; font-size: 14px; }}
        .kpi {{ display: inline-block; padding: 8px 16px; margin: 4px; background: #f0f7f5; border-radius: 8px; font-weight: 700; font-size: 13px; }}
        .health-badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; }}
        .risk-healthy {{ background: #e8f5e9; color: #2e7d32; }}
        .risk-elevated {{ background: #fff8e1; color: #f57f17; }}
        .risk-high {{ background: #fff3e0; color: #e65100; }}
        .risk-critical {{ background: #ffebee; color: #c62828; }}
    </style>
</head>
<body>
    <h1>Achievement Portfolio — {user_name}</h1>
    <p style="color: #888; font-size: 11px;">Generated: {generated_at}</p>

    <div class="summary-box">{summary}</div>

    <div>
        <span class="kpi">Contributions: {total_achievements}</span>
        <span class="kpi">High-Impact Hours: {total_hours}h</span>
    </div>
"""

    # Achievements table
    achievements = portfolio.get("achievements", [])
    if achievements:
        html += """
    <h2>High-Impact Contributions</h2>
    <table>
        <thead><tr>
            <th>Task</th><th>Key Result</th><th>Objective</th><th>Score</th><th>Time</th>
        </tr></thead>
        <tbody>
"""
        for a in achievements:
            time_h = round(a.get("time_spent", 0) / 60, 1)
            html += f"""
            <tr>
                <td><strong>{_escape(a.get("task_title", ""))}</strong></td>
                <td>{_escape(a.get("kr_title", ""))}</td>
                <td>{_escape(a.get("objective_title", ""))}</td>
                <td>{a.get("kr_score", 0):.2f} ({_escape(a.get("kr_score_label", ""))})</td>
                <td>{time_h}h</td>
            </tr>
"""
        html += """
        </tbody>
    </table>
"""

    # Health snapshot
    burnout = portfolio.get("burnout_snapshot", {})
    if burnout:
        risk_label = burnout.get("risk_label", "Unknown")
        risk_class = {
            "Healthy": "risk-healthy",
            "Elevated": "risk-elevated",
            "High": "risk-high",
            "Critical": "risk-critical",
        }.get(risk_label, "risk-healthy")

        html += f"""
    <h2>Health Snapshot</h2>
    <p>
        Burnout Risk: <span class="health-badge {risk_class}">{_escape(risk_label)} ({burnout.get("risk_score", 0)})</span>
        &nbsp; Avg Daily Focus: <strong>{burnout.get("avg_daily_minutes", 0)} min</strong>
        &nbsp; Tasks Completed (14d): <strong>{burnout.get("completed_tasks", 0)}</strong>
    </p>
"""

    html += """
    <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
    <p style="color: #aaa; font-size: 10px;">Generated by the OKR Strategy Engine.</p>
</body>
</html>
"""

    method = _resolve_pdf_method()
    pdf_bytes = generate_pdf_bytes(html, method=method)
    if not pdf_bytes:
        return None
    return BytesIO(pdf_bytes)
