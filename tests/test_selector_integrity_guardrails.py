from __future__ import annotations

import ast
from pathlib import Path


class _SelectorOptionsVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: Path) -> None:
        self.rel_path = rel_path
        self.issues: list[str] = []

    @staticmethod
    def _is_selector_call(node: ast.Call) -> bool:
        func = node.func
        return isinstance(func, ast.Attribute) and func.attr in {"selectbox", "multiselect"}

    @staticmethod
    def _is_keys_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "keys"
            and not node.args
            and not node.keywords
        )

    @classmethod
    def _is_list_of_keys_call(cls, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "list"
            and len(node.args) == 1
            and not node.keywords
            and cls._is_keys_call(node.args[0])
        )

    @classmethod
    def _contains_list_of_keys_call(cls, node: ast.AST) -> bool:
        if cls._is_list_of_keys_call(node):
            return True
        return any(cls._contains_list_of_keys_call(child) for child in ast.iter_child_nodes(node))

    @staticmethod
    def _options_expr(node: ast.Call) -> ast.AST | None:
        for kw in node.keywords:
            if kw.arg == "options":
                return kw.value
        if len(node.args) >= 2:
            return node.args[1]
        return None

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_selector_call(node):
            options_expr = self._options_expr(node)
            if options_expr is not None and self._contains_list_of_keys_call(options_expr):
                self.issues.append(
                    f"{self.rel_path}:{node.lineno} uses list(<dict>.keys()) for selector options; "
                    "prefer ID-backed options + format_func to avoid label-collision bugs"
                )
        self.generic_visit(node)


def test_no_label_keyed_selector_options() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_root = repo_root / "streamlit_app"
    files = [app_root / "app.py", *list((app_root / "src").rglob("*.py"))]

    issues: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        rel = path.relative_to(repo_root)
        visitor = _SelectorOptionsVisitor(rel)
        visitor.visit(tree)
        issues.extend(visitor.issues)

    assert not issues, "Selector integrity guardrail violations:\n" + "\n".join(issues)
