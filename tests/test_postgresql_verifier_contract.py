from __future__ import annotations

import socket

from scripts.verify_postgresql_integration import _available_port


def test_postgresql_verifier_moves_to_an_available_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        preferred = int(occupied.getsockname()[1])

        selected = _available_port(preferred)

    assert selected != preferred
    assert selected > 0


def test_smoke_dsn_variable_survives_conftest_and_reaches_the_test_process():
    """The smoke tests skipped in every CI run because they read a variable conftest overwrites.

    tests/conftest.py sets OKR_DATABASE_URL and DATABASE_URL to sqlite at import. The module must
    read a different variable, and the verifier that launches it must set that variable.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    conftest = (root / "tests" / "conftest.py").read_text(encoding="utf-8")
    smoke = (root / "tests" / "test_postgres_integration_smoke.py").read_text(
        encoding="utf-8"
    )
    verifier = (root / "scripts" / "verify_postgresql_integration.py").read_text(
        encoding="utf-8"
    )

    dsn_env = re.search(r'^DSN_ENV = "([A-Z_]+)"', smoke, re.MULTILINE).group(1)

    assert f'os.environ["{dsn_env}"]' not in conftest
    assert dsn_env not in {"OKR_DATABASE_URL", "DATABASE_URL"}
    assert f'test_env["{dsn_env}"] = database_url' in verifier
    assert 'test_env["OKR_REQUIRE_TEST_POSTGRES_URL"] = "true"' in verifier, (
        "the verifier must make a missing DSN fail rather than skip"
    )
