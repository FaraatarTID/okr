from __future__ import annotations

import ast
from pathlib import Path


def _dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _function_by_name(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function `{name}` not found in app.py")


def test_app_py_stays_thin_and_delegates() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_path = repo_root / "streamlit_app" / "app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Keep app.py as a thin coordinator rather than a UI/logic monolith.
    assert len(source.splitlines()) <= 380, "app.py grew beyond thin-coordinator target"

    disallowed_modules = {"src.ui.dialogs", "src.ui.components", "src.ui.styles"}
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in disallowed_modules:
            violations.append(f"{node.module}:{node.lineno}")
    assert not violations, (
        "app.py should not directly import heavy UI modules:\n" + "\n".join(violations)
    )

    expected_calls = {
        "_get_client_ip": "app_network_helpers.get_client_ip_from_streamlit",
        "render_login": "app_auth_helpers.render_login_from_app",
        "_clear_user_session": "app_auth_helpers.clear_user_session",
        "render_password_reset_gate": "app_auth_helpers.render_password_reset_gate_from_app",
        "render_app": "app_shell_helpers.render_app_from_app",
        "main": "app_entry_helpers.run_main_from_app",
    }

    for fn_name, expected_call in expected_calls.items():
        fn = _function_by_name(tree, fn_name)
        body = list(fn.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        assert len(body) == 1, f"{fn_name} should be a single-statement delegator"
        stmt = body[0]
        assert isinstance(stmt, ast.Return), (
            f"{fn_name} should return helper delegation"
        )
        assert isinstance(stmt.value, ast.Call), (
            f"{fn_name} should call helper function"
        )
        target = _dotted_name(stmt.value.func)
        assert target == expected_call, (
            f"{fn_name} should delegate to {expected_call}, got {target}"
        )
