from __future__ import annotations

import ast
from pathlib import Path


def test_no_duplicate_top_level_function_names() -> None:
    """Prevent silent function overrides within the same module."""
    repo_root = Path(__file__).resolve().parents[1]
    targets = [
        repo_root / "streamlit_app" / "app.py",
        *sorted((repo_root / "streamlit_app" / "src").rglob("*.py")),
    ]
    excluded_dirs = {"venv", "__pycache__", ".pytest_cache", ".venv", "node_modules"}

    issues: list[str] = []
    for path in targets:
        if any(part in excluded_dirs for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen: dict[str, int] = {}
        rel = path.relative_to(repo_root)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            first_line = seen.get(node.name)
            if first_line is None:
                seen[node.name] = node.lineno
            else:
                issues.append(
                    f"{rel}:{node.lineno} duplicates top-level function `{node.name}` "
                    f"(first defined at line {first_line})"
                )

    assert not issues, "Duplicate top-level function definitions found:\n" + "\n".join(
        issues
    )
