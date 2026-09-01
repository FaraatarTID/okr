#!/usr/bin/env python3
"""Ensure CI and justfile script references resolve to repository files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = (ROOT / "justfile", ROOT / ".github" / "workflows")
SCRIPT_REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9_.-])scripts/[A-Za-z0-9_.-]+\.py")


def _input_files(paths: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*") if item.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def missing_references(paths: tuple[Path, ...] = DEFAULT_FILES) -> list[str]:
    missing: list[str] = []
    for source_path in _input_files(paths):
        try:
            display_path = source_path.relative_to(ROOT).as_posix()
        except ValueError:
            display_path = source_path.name
        try:
            source = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            missing.append(f"{display_path}: cannot read reference source: {exc}")
            continue
        for reference in sorted(set(SCRIPT_REFERENCE_RE.findall(source))):
            if not (ROOT / reference).is_file():
                missing.append(
                    f"{display_path}: "
                    f"referenced script does not exist: {reference}"
                )
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        action="append",
        type=Path,
        help="File or directory to scan (repeatable; defaults to justfile and workflows).",
    )
    args = parser.parse_args(argv)
    paths = tuple(path.resolve() for path in args.path) if args.path else DEFAULT_FILES
    errors = missing_references(paths)
    if errors:
        print("CI script reference check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("CI script reference check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
