"""
AI provider health-check command.

Usage:
    python streamlit_app/scripts/ai_provider_health_check.py
    python streamlit_app/scripts/ai_provider_health_check.py --no-probe
    python streamlit_app/scripts/ai_provider_health_check.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AI provider health check.")
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Only validate configuration; skip live provider call.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser


def _print_human_report(report: dict) -> None:
    print("AI Provider Health Check")
    print(f"- Status: {report.get('status')}")
    print(f"- Provider: {report.get('provider')}")
    print(f"- External AI Allowed: {report.get('external_ai_allowed')}")
    print(f"- Configured: {report.get('configured')}")
    print(f"- Config Message: {report.get('config_message')}")
    print(f"- Live Probe Enabled: {report.get('live_probe_enabled')}")
    print(f"- Probe OK: {report.get('probe_ok')}")
    print(f"- Probe Message: {report.get('probe_message')}")


def main() -> int:
    from src.services.ai_provider import run_ai_health_check

    args = _build_parser().parse_args()
    report = run_ai_health_check(live_probe=not args.no_probe)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human_report(report)

    status = str(report.get("status") or "").strip().lower()
    if status in {"not_configured", "probe_failed"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
