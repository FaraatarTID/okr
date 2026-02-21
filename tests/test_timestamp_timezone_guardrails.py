from __future__ import annotations

import ast
from pathlib import Path


def _is_datetime_fromtimestamp_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # datetime.fromtimestamp(...)
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "datetime"
        and func.attr == "fromtimestamp"
    ):
        return True
    # datetime.datetime.fromtimestamp(...)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "datetime"
        and func.value.attr == "datetime"
        and func.attr == "fromtimestamp"
    )


def test_fromtimestamp_usage_is_centralized() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_root = repo_root / "streamlit_app"
    scan_paths = [app_root / "app.py", app_root / "src"]
    allowed = {app_root / "src" / "utils" / "time_utils.py"}

    issues: list[str] = []
    for scan_path in scan_paths:
        paths = [scan_path] if scan_path.is_file() else list(scan_path.rglob("*.py"))
        for path in paths:
            if path in allowed:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(repo_root)
            for node in ast.walk(tree):
                if _is_datetime_fromtimestamp_call(node):
                    issues.append(f"{rel}:{node.lineno} uses datetime.fromtimestamp directly")

    assert not issues, "Unsafe timestamp conversion usage:\n" + "\n".join(issues)
