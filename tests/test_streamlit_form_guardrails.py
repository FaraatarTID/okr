from __future__ import annotations

import ast
from pathlib import Path


class _FormButtonVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: Path) -> None:
        self.rel_path = rel_path
        self._form_depth = 0
        self.issues: list[str] = []

    @staticmethod
    def _is_st_form_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        return (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "st"
            and func.attr == "form"
        )

    @staticmethod
    def _is_button_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "button"
        )

    def visit_With(self, node: ast.With) -> None:
        entered_form = any(self._is_st_form_call(item.context_expr) for item in node.items)
        if entered_form:
            self._form_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        if entered_form:
            self._form_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self._form_depth > 0 and self._is_button_call(node):
            self.issues.append(
                f"{self.rel_path}:{node.lineno} uses .button() inside st.form()"
            )
        self.generic_visit(node)


def test_no_st_button_inside_forms() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_root = repo_root / "streamlit_app"
    files = [app_root / "app.py", *list((app_root / "src").rglob("*.py"))]

    issues: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(repo_root)
        visitor = _FormButtonVisitor(rel)
        visitor.visit(tree)
        issues.extend(visitor.issues)

    assert not issues, "Invalid Streamlit form button usage:\n" + "\n".join(issues)
