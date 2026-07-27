"""Discover the active Jan router context from local logs and API.

Usage:
    python scripts/jan_context.py
    python scripts/jan_context.py --json
    python scripts/jan_context.py --prefer gemma-4-E2B-it
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


ROUTER_LINE_RE = re.compile(r'--port", "(\d+)".*?--api-key", "([^"]+)"', re.DOTALL)
PORT_ONLY_RE = re.compile(r'--port", "(\d+)"', re.DOTALL)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _jan_log_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Jan" / "data" / "logs" / "app.log"
    return Path.home() / ".local" / "share" / "Jan" / "data" / "logs" / "app.log"


def _read_router_state() -> Optional[Tuple[str, str]]:
    log_path = _jan_log_path()
    if not log_path.exists():
        return None

    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    router_lines = [line for line in lines if "Router argv:" in line]
    if not router_lines:
        return None

    # Try each router line from most recent to oldest, looking for one with api-key
    for line in reversed(router_lines):
        # Strip ANSI escape codes that Jan's terminal logging adds
        clean_line = ANSI_ESCAPE_RE.sub("", line)
        match = ROUTER_LINE_RE.search(clean_line)
        if match:
            port = match.group(1).strip()
            api_key = match.group(2).strip()
            if port and api_key:
                return port, api_key

    # Fallback: use most recent line with just port (no api-key)
    clean_line = ANSI_ESCAPE_RE.sub("", router_lines[-1])
    match = PORT_ONLY_RE.search(clean_line)
    if match:
        port = match.group(1).strip()
        if port:
            return port, ""

    return None


def _fetch_models(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"Failed to query Jan models: HTTP {exc.code}: {detail}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to query Jan models: {exc}") from exc

    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list) or not models:
        raise RuntimeError("Jan /v1/models returned no data[] entries.")
    return [model for model in models if isinstance(model, dict)]


def _choose_model(models: List[Dict[str, Any]], prefer: Optional[str]) -> str:
    preferred = str(prefer or "").strip().lower()
    if preferred:
        for model in models:
            model_id = str(model.get("id") or "").strip()
            if model_id.lower() == preferred:
                return model_id
        for model in models:
            model_id = str(model.get("id") or "").strip()
            if preferred in model_id.lower():
                return model_id

    for model in models:
        model_id = str(model.get("id") or "").strip()
        if model_id:
            return model_id
    raise RuntimeError("Could not determine a Jan model ID.")


def _build_report(prefer: Optional[str]) -> Dict[str, Any]:
    state = _read_router_state()
    if state is None:
        return {
            "AI_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
            "JAN_MODEL_IDS": [],
            "JAN_LOG_PATH": str(_jan_log_path()),
        }
    port, api_key = state
    base_url = f"http://127.0.0.1:{port}/v1"
    models = _fetch_models(base_url, api_key)
    model_ids = [
        str(model.get("id") or "").strip()
        for model in models
        if str(model.get("id") or "").strip()
    ]
    selected_model = _choose_model(models, prefer)
    return {
        "AI_BASE_URL": base_url,
        "AI_API_KEY": api_key,
        "AI_MODEL": selected_model,
        "JAN_MODEL_IDS": model_ids,
        "JAN_LOG_PATH": str(_jan_log_path()),
    }


def _print_env(report: Dict[str, Any]) -> None:
    print(f"AI_BASE_URL={report['AI_BASE_URL']}")
    api_key = str(report.get("AI_API_KEY") or "")
    masked = (
        f"****{api_key[-4:]}"
        if len(api_key) > 4
        else "****"
        if api_key
        else "(not set)"
    )
    print(f"AI_API_KEY={masked}")
    print(f"AI_MODEL={report['AI_MODEL']}")
    model_ids = report.get("JAN_MODEL_IDS") or []
    if isinstance(model_ids, list) and model_ids:
        print(f"JAN_MODEL_IDS={','.join(str(item) for item in model_ids)}")
    print(f"JAN_LOG_PATH={report['JAN_LOG_PATH']}")


def _update_env_file(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines: List[str] = []
    if path.exists():
        existing_lines = path.read_text(
            encoding="utf-8-sig", errors="ignore"
        ).splitlines()

    replacements = {
        "AI_BASE_URL": str(report["AI_BASE_URL"]),
        "AI_API_KEY": str(report["AI_API_KEY"]),
        "AI_MODEL": str(report["AI_MODEL"]),
    }
    seen_keys = set()
    updated_lines: List[str] = []

    for raw_line in existing_lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated_lines.append(line)
            continue
        key, _, value = line.partition("=")
        normalized_key = key.strip()
        if normalized_key in replacements:
            updated_lines.append(f"{normalized_key}={replacements[normalized_key]}")
            seen_keys.add(normalized_key)
        else:
            updated_lines.append(line)

    for key in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"):
        if key not in seen_keys:
            updated_lines.append(f"{key}={replacements[key]}")

    path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover the active Jan router context."
    )
    parser.add_argument(
        "--prefer",
        help="Prefer a model ID containing this text (exact match first, then substring).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    parser.add_argument(
        "--powershell",
        action="store_true",
        help="Print PowerShell env assignments.",
    )
    parser.add_argument(
        "--write-env-file",
        metavar="PATH",
        help="Write AI_* values into the specified .env file.",
    )
    args = parser.parse_args()

    report = _build_report(args.prefer)

    if not report.get("AI_BASE_URL"):
        print(
            "[WARN] Jan AI router not found or not running; skipping context refresh.",
            file=sys.stderr,
        )
        return 0

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.powershell:
        print(f'$env:AI_BASE_URL = "{report["AI_BASE_URL"]}"')
        api_key = str(report.get("AI_API_KEY") or "")
        masked = (
            f"****{api_key[-4:]}"
            if len(api_key) > 4
            else "****"
            if api_key
            else "(not set)"
        )
        print(f'$env:AI_API_KEY = "{masked}"')
        print(f'$env:AI_MODEL = "{report["AI_MODEL"]}"')
    else:
        _print_env(report)

    if args.write_env_file:
        _update_env_file(Path(args.write_env_file), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
