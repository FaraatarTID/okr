"""Probe Supabase HTTPS connectivity when Postgres TCP ports are blocked.

This script validates:
1) HTTPS reachability to Supabase project URL (port 443)
2) REST endpoint accessibility
3) API key acceptance (optional)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _normalize_base_url(raw_url: str) -> str:
    value = str(raw_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("Missing Supabase URL.")
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme:
        value = f"https://{value}"
        parsed = urllib.parse.urlparse(value)
    if parsed.scheme.lower() != "https":
        raise ValueError("Supabase URL must use https://")
    if not parsed.netloc:
        raise ValueError("Supabase URL host is missing.")
    return value


def _request(url: str, *, api_key: str | None, timeout: float) -> tuple[bool, int, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["apikey"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    import ssl

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
            code = int(resp.status)
            body = resp.read(512).decode("utf-8", errors="replace")
            return True, code, body
    except urllib.error.HTTPError as exc:
        # HTTP errors still confirm HTTPS reachability.
        body = exc.read(512).decode("utf-8", errors="replace")
        return True, int(exc.code), body
    except Exception as exc:  # network failure
        return False, 0, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Supabase HTTPS connectivity probe")
    parser.add_argument(
        "--url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Supabase project URL (default: SUPABASE_URL env)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_ANON_KEY", "")
        ),
        help="Supabase API key (default: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY env)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Request timeout seconds (default: 8)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    try:
        base_url = _normalize_base_url(args.url)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        print("Set SUPABASE_URL, for example: https://<project-ref>.supabase.co")
        return 2

    api_key = str(args.api_key or "").strip() or None
    rest_url = f"{base_url}/rest/v1/"
    health_url = f"{base_url}/auth/v1/health"

    rest_ok, rest_code, rest_body = _request(
        rest_url, api_key=api_key, timeout=args.timeout
    )
    auth_ok, auth_code, auth_body = _request(
        health_url, api_key=None, timeout=args.timeout
    )

    result = {
        "supabase_url": base_url,
        "rest": {
            "reachable": rest_ok,
            "status_code": rest_code,
            "body_preview": rest_body[:200],
        },
        "auth_health": {
            "reachable": auth_ok,
            "status_code": auth_code,
            "body_preview": auth_body[:200],
        },
        "api_key_provided": bool(api_key),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("[INFO] Supabase HTTPS probe")
        print(f"       URL: {base_url}")
        print(f"       REST: reachable={rest_ok} status={rest_code}")
        print(f"       AUTH health: reachable={auth_ok} status={auth_code}")
        if not api_key:
            print(
                "[WARN] No API key supplied. Set SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY."
            )

    # success if at least one HTTPS endpoint is reachable
    if rest_ok or auth_ok:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
