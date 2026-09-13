#!/usr/bin/env python3
"""Reject mutable container tags in release and deployment configuration."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_MUTABLE_TAG_RE = re.compile(r":(?:latest|stable|main|master)(?:[\s\"'`]|$)", re.IGNORECASE)


def find_mutable_references(root: Path = ROOT) -> list[str]:
    candidates = sorted(
        path
        for base in (root / "deploy", root / ".github" / "workflows")
        for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml", ".env"}
    )
    failures: list[str] = []
    for path in candidates:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith("#"):
                continue
            if _MUTABLE_TAG_RE.search(line):
                failures.append(f"{path.relative_to(root).as_posix()}:{number}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    failures = find_mutable_references(args.root.resolve())
    if failures:
        print("[IMMUTABLE-DEPLOY] Mutable image references detected:")
        for failure in failures:
            print(f"- {failure}")
        print("Use the commit-SHA tag plus its verified @sha256 digest.")
        return 1
    print("[IMMUTABLE-DEPLOY] Deployment configuration contains no mutable image tags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
