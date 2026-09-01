#!/usr/bin/env python3
"""Check that service packages keep their intended dependency boundaries."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKSPACES = {"spa-bff": "okr-spa-bff", "spa-web": "okr-spa-web"}


def _production_python_paths() -> list[Path]:
    paths = [path for path in ROOT_DIR.glob("*.py") if path.name != "app.py"]
    for directory in ("src", "backend_app", "scripts"):
        paths.extend((ROOT_DIR / directory).rglob("*.py"))
    return paths


def _python_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def main() -> int:
    errors: list[str] = []
    for path in _production_python_paths():
        try:
            imports = _python_imports(path)
        except SyntaxError as exc:
            errors.append(f"{path}: cannot parse Python source: {exc}")
            continue
        if "backend_app" in imports:
            if path.is_relative_to(ROOT_DIR / "src"):
                errors.append(f"{path.relative_to(ROOT_DIR)}: src must not import backend_app")
        if "app" in imports:
            errors.append(
                f"{path.relative_to(ROOT_DIR)}: production code must not import root app.py facade"
            )

    workspace_names = set(WORKSPACES.values())
    for directory, package_name in WORKSPACES.items():
        manifest_path = ROOT_DIR / directory / "package.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared: set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            declared.update(manifest.get(section, {}))
        for dependency in sorted(declared & workspace_names):
            if dependency != package_name:
                errors.append(
                    f"{manifest_path.relative_to(ROOT_DIR)}: workspace packages must not depend on {dependency}"
                )

    if errors:
        print("Import boundary check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Import boundary check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
