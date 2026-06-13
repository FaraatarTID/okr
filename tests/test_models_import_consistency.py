from __future__ import annotations

import ast
from pathlib import Path


def test_models_import_path_is_consistent() -> None:
    """Prevent mapper collisions from mixed module import paths."""
    root = Path(__file__).resolve().parents[1]
    excluded_dirs = {"venv", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
    py_files = [
        path for path in root.rglob("*.py") if excluded_dirs.isdisjoint(path.parts)
    ]

    issues: list[str] = []

    for path in py_files:
        rel = path.relative_to(root)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module == "models":
                    issues.append(
                        f"{rel}:{node.lineno} imports models via `{module}`; use `src.models` only"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = str(alias.name or "")
                    if name == "models":
                        issues.append(
                            f"{rel}:{node.lineno} imports `{name}`; use `src.models` only"
                        )

    assert not issues, "Model import path inconsistency detected:\n" + "\n".join(issues)
