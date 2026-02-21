from __future__ import annotations

import ast
from pathlib import Path


def _is_datetime_utcnow_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # datetime.utcnow(...)
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "datetime"
        and func.attr == "utcnow"
    ):
        return True
    # datetime.datetime.utcnow(...)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "datetime"
        and func.value.attr == "datetime"
        and func.attr == "utcnow"
    )


def test_runtime_code_avoids_datetime_utcnow() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_root = repo_root / "streamlit_app"
    paths = [app_root / "app.py", *list((app_root / "src").rglob("*.py"))]

    issues: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(repo_root)
        for node in ast.walk(tree):
            if _is_datetime_utcnow_call(node):
                issues.append(f"{rel}:{node.lineno} uses datetime.utcnow() directly")

    assert not issues, "Deprecated datetime.utcnow usage found:\n" + "\n".join(issues)
