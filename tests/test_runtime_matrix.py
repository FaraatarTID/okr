from pathlib import Path

from scripts.verify_runtime_matrix import verify_matrix


def test_repository_runtime_matrix_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    assert verify_matrix(root / "deploy/runtime-matrix.json") == []


def test_runtime_matrix_rejects_wrong_worker_entrypoint(tmp_path: Path) -> None:
    matrix = tmp_path / "runtime-matrix.json"
    matrix.write_text(
        '{"schema_version": 1, "python": "3.11", "node": "22", "postgresql": "16", '
        '"migration_policy": "one-off", "entrypoints": {"api": "python -m backend_app.run_api", '
        '"worker": "wrong", "bff": "npm run start", "web": "npm run start"}, '
        '"health": {"api": "/healthz", "bff": "/healthz", "web": "/"}}',
        encoding="utf-8",
    )

    assert verify_matrix(matrix)
