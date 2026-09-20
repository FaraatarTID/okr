#!/usr/bin/env python3
"""Compare non-secret configuration shape between SaaS and staging templates."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SECRET = re.compile(r"(?:PASSWORD|TOKEN|SECRET|API_KEY|DATABASE_URL)", re.IGNORECASE)
_URL = re.compile(r"(?:URL|ORIGIN|ADDRESS|HOST)", re.IGNORECASE)


def _parse(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _kind(key: str, value: str) -> str:
    if _SECRET.search(key):
        return "secret"
    if value.lower() in {"true", "false"}:
        return "boolean"
    if value.isdigit():
        return "integer"
    if _URL.search(key):
        return "endpoint"
    return "string"


def check_parity(canonical: Path, staging: Path) -> list[str]:
    try:
        source = _parse(canonical)
        target = _parse(staging)
    except (OSError, UnicodeDecodeError) as exc:
        return [f"unable to read configuration template: {type(exc).__name__}"]
    failures: list[str] = []
    for key, source_value in sorted(source.items()):
        if key not in target:
            failures.append(f"staging template is missing configuration key {key}")
            continue
        if _kind(key, source_value) != _kind(key, target[key]):
            failures.append(f"configuration type policy differs for {key}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canonical", type=Path, default=ROOT / "deploy/docker/.env.saas.example"
    )
    parser.add_argument(
        "--staging", type=Path, default=ROOT / "deploy/darkube/prerelease/.env.example"
    )
    args = parser.parse_args(argv)
    failures = check_parity(args.canonical, args.staging)
    if failures:
        print("[CONFIG-PARITY] Staging configuration shape check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[CONFIG-PARITY] Staging configuration shape matches the SaaS contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
