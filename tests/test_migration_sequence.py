from pathlib import Path

from scripts import verify_migration_sequence


def test_migration_sequence_runs_expected_commands(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["cwd"] == tmp_path
        return Result()

    monkeypatch.setattr(verify_migration_sequence.subprocess, "run", fake_run)

    assert verify_migration_sequence.run_sequence(root=tmp_path) == 0
    assert commands == [
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "current"],
        ["uv", "run", "alembic", "upgrade", "head"],
    ]
