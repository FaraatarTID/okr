from pathlib import Path

from scripts.verify_migration_safety import validate


FIXTURES = Path(__file__).parent / "fixtures" / "migration_safety"


def test_representative_additive_backfill_and_contract_revisions_pass(
    tmp_path: Path,
) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    for kind in ("additive", "backfill", "contract"):
        source = next((FIXTURES / kind).glob("*.py"))
        (versions / source.name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    assert validate(versions, tmp_path / "exceptions") == []


def test_destructive_revision_without_approved_maintenance_exception_is_rejected(
    tmp_path: Path,
) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    source = next((FIXTURES / "unsafe_destructive").glob("*.py"))
    (versions / source.name).write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    errors = validate(versions, tmp_path / "exceptions")

    assert any("requires an approved exception_record" in error for error in errors)


def test_production_fleet_rejects_maintenance_window_revision(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    exceptions = tmp_path / "exceptions"
    versions.mkdir()
    exceptions.mkdir()
    (versions / "maintenance.py").write_text(
        """revision = "maintenance"\nMIGRATION_METADATA = {"additive": False, "backfill": False, "contract": True, "destructive": True, "locking_risk": True, "reversible": False, "compatible_with_previous_release": False, "maintenance_window_only": True, "exception_record": "approved.json"}\n""",
        encoding="utf-8",
    )
    (exceptions / "approved.json").write_text(
        '{"status":"approved", "approved_by":"dba", "maintenance_window":"2026-10-01 UTC"}',
        encoding="utf-8",
    )

    errors = validate(
        versions, exceptions, selected_revision="maintenance", production_fleet=True
    )

    assert any(
        "cannot be run in a production fleet rollout" in error for error in errors
    )
