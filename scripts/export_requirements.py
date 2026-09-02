#!/usr/bin/env python3
"""Generate the legacy pip requirements export from pyproject declarations."""

from __future__ import annotations

import argparse

from check_dependency_manifest import ROOT, _dependencies_from_pyproject


HEADER = (
    "# GENERATED FILE. Do not edit manually; run python scripts/export_requirements.py.\n"
    "# Source authority: pyproject.toml and uv.lock.\n"
)
TARGET = ROOT / "backend_app/requirements.txt"


def rendered_requirements() -> str:
    values = _dependencies_from_pyproject()
    return HEADER + "".join(f"{values[name]}\n" for name in sorted(values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the export is stale")
    args = parser.parse_args()
    expected = rendered_requirements()
    actual = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    if args.check:
        if actual != expected:
            print("[REQUIREMENTS-EXPORT] generated compatibility export is stale")
            return 1
        print("[REQUIREMENTS-EXPORT] compatibility export is current")
        return 0
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print(f"[REQUIREMENTS-EXPORT] wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
