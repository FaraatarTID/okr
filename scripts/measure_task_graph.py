#!/usr/bin/env python3
"""Measure repository tasks for task-graph and cache decisions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKS: dict[str, tuple[str, ...]] = {
    "python-tests": ("python", "-m", "pytest", "-q"),
    "javascript-tests": ("npm", "test"),
    "typecheck": ("npm", "run", "typecheck"),
    "build": ("npm", "run", "build"),
    "contracts": ("python", "scripts/check_openapi_drift.py"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        action="append",
        choices=sorted(TASKS),
        help="Task to measure; may be supplied more than once (default: all).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path; stdout is always written.",
    )
    return parser.parse_args()


def measure(name: str, command: tuple[str, ...]) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, check=False)
    duration_seconds = round(time.perf_counter() - started, 3)
    return {
        "task": name,
        "command": list(command),
        "duration_seconds": duration_seconds,
        "exit_code": completed.returncode,
    }


def main() -> int:
    args = parse_args()
    selected = args.task or sorted(TASKS)
    results = [measure(name, TASKS[name]) for name in selected]
    payload = {"root": str(ROOT), "results": results}
    rendered = json.dumps(payload, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if all(result["exit_code"] == 0 for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
