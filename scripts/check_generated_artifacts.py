#!/usr/bin/env python3
"""Fail CI when generated artifacts are accidentally tracked by git.

Tracked paths covered:
- pytest junit artifacts (pytest-results.xml, pytest-results-*.xml)
- coverage outputs (coverage/, coverage-summary.json, htmlcov/, .coverage*)
- JS/TS build outputs (.next/, dist/, build/, *.tsbuildinfo, .cache/)
- Python caches (__pycache__/, *.pyc, .pytest_cache/, .mypy_cache/, .ruff_cache/)
- Local env files (.env variants except examples) and tmp/logs working dirs

The checker uses ``git ls-files`` so it only inspects tracked paths; local
untracked outputs are governed by .gitignore instead.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)pytest-results\.xml$"),
    re.compile(r"(^|/)pytest-results-[^/]*\.xml$"),
    re.compile(r"(^|/)[\w-]*pytest-results\.xml$"),
    re.compile(r"(^|/)pytest-spa-e2e-results\.xml$"),
    re.compile(r"(^|/)\.coverage(\..*)?$"),
    re.compile(r"(^|/)coverage\.xml$"),
    re.compile(r"(^|/)coverage-summary\.json$"),
    re.compile(r"(^|/)htmlcov/"),
    re.compile(r"(^|/)coverage/"),
    re.compile(r"(^|/)\.next/"),
    re.compile(r"(^|/)dist/"),
    re.compile(r"(^|/)build/"),
    re.compile(r"\.tsbuildinfo$"),
    re.compile(r"(^|/)\.cache/"),
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.py[cod]$"),
    re.compile(r"(^|/)\.pytest_cache/"),
    re.compile(r"(^|/)\.mypy_cache/"),
    re.compile(r"(^|/)\.ruff_cache/"),
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)\.venv/"),
    re.compile(r"(^|/)(tmp|logs|\.test-artifacts)/"),
    re.compile(r"\.log$"),
    re.compile(r"(^|/)\.env(\..*)?$"),
)

# .env.example files are intentional tracked examples, not local secrets.
ALLOWLIST = (
    re.compile(r"\.env\.example$"),
    re.compile(r"\.env\.[A-Za-z0-9_.-]*\.example$"),
)


def _tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def find_violations(tracked: list[str]) -> list[str]:
    violations: list[str] = []
    for path in tracked:
        if any(pattern.search(path) for pattern in ALLOWLIST):
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(path):
                violations.append(f"{path} (matches {pattern.pattern})")
                break
    return violations


def main() -> int:
    try:
        tracked = _tracked_files()
    except Exception as exc:  # noqa: BLE001
        print(f"Generated artifact check skipped: cannot list git files: {exc}")
        return 0
    violations = find_violations(tracked)
    if violations:
        print("Generated artifact check failed: tracked generated artifacts found:")
        for violation in sorted(violations):
            print(f"- {violation}")
        print("Remediation: `git rm --cached <path>` and ensure .gitignore covers it.")
        return 1
    print(f"Generated artifact check passed ({len(tracked)} tracked files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
