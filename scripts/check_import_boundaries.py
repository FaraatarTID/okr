#!/usr/bin/env python3
"""Check that service packages keep their intended dependency boundaries."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKSPACES = {"spa-bff": "okr-spa-bff", "spa-web": "okr-spa-web"}
DELIVERY_FRAMEWORK_MODULES = frozenset({"fastapi", "flask", "starlette", "streamlit"})


def _production_python_paths() -> list[Path]:
    paths = list(ROOT_DIR.glob("*.py"))
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


def _boundary_errors(path: Path, imports: set[str]) -> list[str]:
    """Return violations for one Python source file.

    The root app module is retired, so the forbidden import is the module named
    exactly ``app`` rather than an arbitrary package whose name merely contains
    that token. Delivery frameworks are forbidden only in ``src``;
    ``backend_app`` is the delivery boundary that owns them.
    """
    errors: list[str] = []
    relative_path = path.relative_to(ROOT_DIR)
    is_src = path.is_relative_to(ROOT_DIR / "src")

    if is_src and "backend_app" in imports:
        errors.append(f"{relative_path}: src must not import backend_app")

    if is_src:
        for module in sorted(imports & DELIVERY_FRAMEWORK_MODULES):
            errors.append(
                f"{relative_path}: src must not import delivery framework {module}"
            )

    if "app" in imports:
        errors.append(
            f"{relative_path}: production code must not import root app.py facade"
        )
    return errors


def main() -> int:
    errors: list[str] = []
    for path in _production_python_paths():
        try:
            imports = _python_imports(path)
        except SyntaxError as exc:
            errors.append(f"{path}: cannot parse Python source: {exc}")
            continue
        errors.extend(_boundary_errors(path, imports))

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
