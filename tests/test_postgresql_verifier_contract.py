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


class _Clock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def time(self):
        # Advance a little on every read so a loop that forgets to sleep still reaches the
        # deadline and fails an assertion, instead of hanging the run.
        self.now += 0.001
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_wait_for_postgres_retries_until_a_query_succeeds():
    """A port that accepts sockets before the server is ready must not count as ready.

    CI's Docker proxy accepted TCP while PostgreSQL was still restarting after first boot, and the
    first connections failed with "server closed the connection unexpectedly".
    """
    from scripts.verify_postgresql_integration import _wait_for_postgres

    clock = _Clock()
    attempts = []

    def connect():
        attempts.append(1)
        if len(attempts) < 4:
            raise OSError("server closed the connection unexpectedly")

    assert _wait_for_postgres(
        "postgresql+psycopg2://x",
        30,
        connect=connect,
        sleep=clock.sleep,
        clock=clock.time,
    )
    assert len(attempts) == 4
    assert len(clock.slept) == 3


def test_wait_for_postgres_gives_up_at_the_deadline():
    from scripts.verify_postgresql_integration import _wait_for_postgres

    clock = _Clock()

    def connect():
        raise OSError("never ready")

    assert not _wait_for_postgres(
        "postgresql+psycopg2://x",
        5,
        connect=connect,
        sleep=clock.sleep,
        clock=clock.time,
    )
    assert clock.now >= 5


def test_verifier_waits_for_a_query_and_tears_down_with_the_start_environment():
    """Both lines come from the first CI run of this step and are pinned as text."""
    from pathlib import Path

    verifier = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "verify_postgresql_integration.py"
    ).read_text(encoding="utf-8")

    assert "_wait_for_postgres(database_url, timeout_seconds=80)" in verifier
    # compose interpolates required variables on `rm` too; without env it failed with
    # "OKR_BACKEND_SERVICE_TOKEN must be set" and left the container behind.
    teardown = verifier.split('command=["rm", "--stop"', 1)[1].split(")", 1)[0]
    assert "env=env" in teardown
