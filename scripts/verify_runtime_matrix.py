#!/usr/bin/env python3
"""Validate the versioned CI, local, and release runtime contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENTRYPOINTS = {"api", "worker", "bff", "web"}
REQUIRED_HEALTH = {"api", "bff", "web"}


def verify_matrix(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["runtime matrix is missing or invalid JSON"]
    failures: list[str] = []
    if payload.get("schema_version") != 1:
        failures.append("runtime matrix schema_version must be 1")
    for key in ("python", "node", "postgresql", "migration_policy"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            failures.append(f"runtime matrix field {key!r} is required")
    entrypoints = payload.get("entrypoints")
    if not isinstance(entrypoints, dict) or set(entrypoints) != REQUIRED_ENTRYPOINTS:
        failures.append(
            "runtime matrix must define api, worker, bff, and web entrypoints"
        )
    elif (
        entrypoints["api"] != "python -m backend_app.run_api"
        or entrypoints["worker"] != "python -m backend_app.worker"
    ):
        failures.append("API and worker entrypoints do not match the release contract")
    health = payload.get("health")
    if not isinstance(health, dict) or set(health) != REQUIRED_HEALTH:
        failures.append("runtime matrix must define api, bff, and web health paths")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    failures = verify_matrix(args.root.resolve() / "deploy/runtime-matrix.json")
    if failures:
        print("[RUNTIME-MATRIX] Contract failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[RUNTIME-MATRIX] Versioned runtime contract passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
