from __future__ import annotations

import ast
from pathlib import Path


def test_models_use_lambda_relationship_resolution() -> None:
    """Guard against hot-reload mapper ambiguity from string class lookup."""
    repo_root = Path(__file__).resolve().parents[1]
    models_path = repo_root / "streamlit_app" / "src" / "models.py"
    tree = ast.parse(models_path.read_text(encoding="utf-8"))

    issues: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Relationship"
        ):
            continue
        has_back_populates = any(keyword.arg == "back_populates" for keyword in node.keywords)
        has_sa_relationship = any(keyword.arg == "sa_relationship" for keyword in node.keywords)
        if has_back_populates and not has_sa_relationship:
            issues.append(
                f"{models_path.relative_to(repo_root)}:{node.lineno} "
                "uses Relationship(back_populates=...) without sa_relationship"
            )

    assert not issues, "Unsafe relationship declarations found:\n" + "\n".join(issues)


def test_models_avoid_string_based_relationship_kwargs() -> None:
    """Block relationship kwarg string expressions that are fragile under reload."""
    repo_root = Path(__file__).resolve().parents[1]
    models_path = repo_root / "streamlit_app" / "src" / "models.py"
    tree = ast.parse(models_path.read_text(encoding="utf-8"))

    issues: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "relationship"
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg == "foreign_keys" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                issues.append(
                    f"{models_path.relative_to(repo_root)}:{node.lineno} "
                    "uses string foreign_keys in relationship(...); prefer callable/list refs"
                )

    assert not issues, "String-based relationship kwargs found:\n" + "\n".join(issues)
