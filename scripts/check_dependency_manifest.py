#!/usr/bin/env python3
"""Ensure the pip compatibility export matches the uv dependency authority."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PINNED = re.compile(r"^([A-Za-z0-9_.-]+)==([^;#\s]+)")


def _name(value: str) -> str:
    return re.split(r"[<>=!~;\s]", value, maxsplit=1)[0].replace("_", "-").lower()


def _dependencies_from_pyproject() -> dict[str, str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    values = list(data["project"]["dependencies"])
    values.extend(data["dependency-groups"]["dev"])
    result: dict[str, str] = {}
    for value in values:
        match = _PINNED.match(value)
        if not match:
            raise ValueError(f"Unpinned or unsupported dependency declaration: {value}")
        name = _name(match.group(1))
        result[name] = f"{name}=={match.group(2)}"
    return result


def _dependencies_from_requirements() -> dict[str, str]:
    result: dict[str, str] = {}
    lines = (ROOT / "backend_app/requirements.txt").read_text(encoding="utf-8").splitlines()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _PINNED.match(line)
        if not match:
            raise ValueError(f"Unpinned or unsupported requirements entry: {line}")
        name = _name(match.group(1))
        result[name] = f"{name}=={match.group(2)}"
    return result


def _locked_versions() -> dict[str, str]:
    data = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {
        _name(package["name"]): package["version"]
        for package in data.get("package", [])
        if isinstance(package, dict) and "name" in package and "version" in package
    }


def check() -> list[str]:
    if not (ROOT / "uv.lock").is_file():
        return ["uv.lock is missing"]
    try:
        expected = _dependencies_from_pyproject()
        actual = _dependencies_from_requirements()
        locked = _locked_versions()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return [str(exc)]
    failures = [
        f"{key}: authority={expected.get(key)!r}, compatibility={actual.get(key)!r}"
        for key in sorted(set(expected) | set(actual))
        if expected.get(key) != actual.get(key)
    ]
    failures.extend(
        f"{key}: declared={value!r}, locked={locked.get(key)!r}"
        for key, value in sorted(expected.items())
        if locked.get(key) != value.split("==", 1)[1]
    )
    return failures


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    failures = check()
    if failures:
        print("[DEPENDENCY-MANIFEST] drift detected:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[DEPENDENCY-MANIFEST] compatibility export matches uv authority.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
