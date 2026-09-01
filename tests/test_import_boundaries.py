from __future__ import annotations

from pathlib import Path

from scripts.check_import_boundaries import _boundary_errors, _python_imports


ROOT = Path(__file__).resolve().parents[1]


def test_src_rejects_backend_and_delivery_framework_imports(tmp_path, monkeypatch):
    path = tmp_path / "src" / "service.py"
    path.parent.mkdir()
    path.write_text(
        "from backend_app import main\nfrom fastapi import FastAPI\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.check_import_boundaries.ROOT_DIR", tmp_path)

    errors = _boundary_errors(path, _python_imports(path))
    relative = str(Path("src") / "service.py")

    assert errors == [
        f"{relative}: src must not import backend_app",
        f"{relative}: src must not import delivery framework fastapi",
    ]


def test_backend_app_may_import_delivery_frameworks(tmp_path, monkeypatch):
    path = tmp_path / "backend_app" / "main.py"
    path.parent.mkdir()
    path.write_text("from fastapi import FastAPI\n", encoding="utf-8")
    monkeypatch.setattr("scripts.check_import_boundaries.ROOT_DIR", tmp_path)

    assert _boundary_errors(path, _python_imports(path)) == []


def test_root_app_facade_import_is_rejected_but_similar_module_is_not(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("scripts.check_import_boundaries.ROOT_DIR", tmp_path)
    facade = tmp_path / "src" / "service.py"
    facade.parent.mkdir()
    facade.write_text("import app\n", encoding="utf-8")
    similarly_named = tmp_path / "src" / "application.py"
    similarly_named.write_text("import application\n", encoding="utf-8")
    relative = str(Path("src") / "service.py")

    assert _boundary_errors(facade, _python_imports(facade)) == [
        f"{relative}: production code must not import root app.py facade"
    ]
    assert _boundary_errors(similarly_named, _python_imports(similarly_named)) == []
