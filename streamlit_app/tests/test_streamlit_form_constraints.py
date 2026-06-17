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
        self._form_submit_stack: list[bool] = []
        self.button_issues: list[str] = []
        self.submit_outside_form_issues: list[str] = []
        self.nested_form_issues: list[str] = []
        self.form_without_submit_issues: list[str] = []

    def visit_With(self, node: ast.With) -> None:
        enters_form = any(
            _is_streamlit_form_call(item.context_expr) for item in node.items
        )
        if enters_form and self.form_depth > 0:
            self.nested_form_issues.append(
                f"{self.path}:{node.lineno} contains nested `st.form` blocks"
            )
        if enters_form:
            self.form_depth += 1
            self._form_submit_stack.append(False)
        for stmt in node.body:
            self.visit(stmt)
        if enters_form:
            had_submit = self._form_submit_stack.pop()
            if not had_submit:
                self.form_without_submit_issues.append(
                    f"{self.path}:{node.lineno} has `st.form` without `st.form_submit_button`"
                )
            self.form_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self.form_depth > 0 and _is_disallowed_button_call(node):
            callsite = ast.unparse(node.func)
            self.button_issues.append(
                f"{self.path}:{node.lineno} uses `{callsite}` inside `st.form`"
            )
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "form_submit_button"
        ):
            if self.form_depth == 0:
                self.submit_outside_form_issues.append(
                    f"{self.path}:{node.lineno} uses `st.form_submit_button` outside `st.form`"
                )
            elif self._form_submit_stack:
                self._form_submit_stack[-1] = True
        self.generic_visit(node)


def test_streamlit_form_widget_constraints() -> None:
    app_root = Path(__file__).resolve().parents[1]
    excluded_dirs = {"tests", "venv", "__pycache__", ".pytest_cache"}
    py_files = [
        path for path in app_root.rglob("*.py") if excluded_dirs.isdisjoint(path.parts)
    ]

    button_issues: list[str] = []
    submit_outside_form_issues: list[str] = []
    nested_form_issues: list[str] = []
    form_without_submit_issues: list[str] = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visitor = _FormButtonVisitor(path.relative_to(app_root.parent))
        visitor.visit(tree)
        button_issues.extend(visitor.button_issues)
        submit_outside_form_issues.extend(visitor.submit_outside_form_issues)
        nested_form_issues.extend(visitor.nested_form_issues)
        form_without_submit_issues.extend(visitor.form_without_submit_issues)

    assert not button_issues, (
        "Disallowed button widgets found inside st.form:\n" + "\n".join(button_issues)
    )
    assert not submit_outside_form_issues, (
        "`st.form_submit_button` must be inside st.form:\n"
        + "\n".join(submit_outside_form_issues)
    )
    assert not nested_form_issues, (
        "Nested Streamlit forms are not allowed:\n" + "\n".join(nested_form_issues)
    )
    assert not form_without_submit_issues, (
        "Every st.form must include st.form_submit_button:\n"
        + "\n".join(form_without_submit_issues)
    )
