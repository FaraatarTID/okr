import ast
from pathlib import Path


def _is_streamlit_form_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
        and node.func.attr == "form"
    )


def _is_disallowed_button_call(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    attr = node.func.attr
    return "button" in attr and attr != "form_submit_button"


class _FormButtonVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.form_depth = 0
        self.issues: list[str] = []

    def visit_With(self, node: ast.With) -> None:
        enters_form = any(_is_streamlit_form_call(item.context_expr) for item in node.items)
        if enters_form:
            self.form_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        if enters_form:
            self.form_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self.form_depth > 0 and _is_disallowed_button_call(node):
            callsite = ast.unparse(node.func)
            self.issues.append(f"{self.path}:{node.lineno} uses `{callsite}` inside `st.form`")
        self.generic_visit(node)


def test_no_non_submit_buttons_inside_streamlit_forms() -> None:
    app_root = Path(__file__).resolve().parents[1]
    excluded_dirs = {"tests", "venv", "__pycache__", ".pytest_cache"}
    py_files = [
        path
        for path in app_root.rglob("*.py")
        if excluded_dirs.isdisjoint(path.parts)
    ]

    issues: list[str] = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visitor = _FormButtonVisitor(path.relative_to(app_root.parent))
        visitor.visit(tree)
        issues.extend(visitor.issues)

    assert not issues, "Disallowed button widgets found inside st.form:\n" + "\n".join(issues)
