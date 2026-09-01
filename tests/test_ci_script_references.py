from __future__ import annotations

from pathlib import Path

from scripts.check_ci_script_references import missing_references


def test_repository_ci_script_references_resolve() -> None:
    root = Path(__file__).resolve().parents[1]
    assert missing_references((root / "justfile", root / ".github" / "workflows")) == []


def test_missing_script_reference_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "workflow.yml"
    source.write_text("run: python scripts/renamed_gate.py\n", encoding="utf-8")

    errors = missing_references((source,))

    assert len(errors) == 1
    assert errors[0].endswith(
        "workflow.yml: referenced script does not exist: scripts/renamed_gate.py"
    )
