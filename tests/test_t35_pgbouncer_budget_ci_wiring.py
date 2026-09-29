"""CI must run the budget through an actual transaction-mode PgBouncer."""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_backend_quality_starts_pinned_pooler_with_mounted_transaction_config():
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["backend-quality"]
    assert "postgres" in job["services"]
    assert job["env"]["OKR_REQUIRE_TEST_PGBOUNCER_URL"] == "true"
    pooler_url = urlsplit(job["env"]["OKR_TEST_PGBOUNCER_URL"])
    postgres_url = urlsplit(job["env"]["OKR_TEST_POSTGRES_URL"])
    assert pooler_url.scheme == "postgresql+psycopg2"
    assert pooler_url.hostname == "localhost" and pooler_url.port == 6543
    assert postgres_url.hostname == "localhost" and postgres_url.port == 5432
    assert pooler_url.path == postgres_url.path == "/okr"
    assert pooler_url.netloc != postgres_url.netloc

    steps = job["steps"]
    startup = next(step for step in steps if step["name"] == "Start PgBouncer")
    command = startup["run"]
    assert "pgbouncer/pgbouncer:1.25.2@sha256:" in command
    assert "tests/support/pgbouncer/pgbouncer.ini" in command
    assert "job.services.postgres.id" in command
    assert "--network" in command and "-p 127.0.0.1:6543:6432" in command
    assert "pgbouncer" in command
    assert steps.index(startup) < next(
        i for i, step in enumerate(steps) if step["name"] == "Python Test Suite"
    )

    config = ConfigParser()
    assert config.read(ROOT / "tests/support/pgbouncer/pgbouncer.ini")
    assert config["pgbouncer"]["pool_mode"] == "transaction"
    assert config["pgbouncer"]["listen_port"] == "6432"
    assert config["databases"]["*"]


def test_backend_quality_retains_passing_pooler_measurements_in_junit_artifact():
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["backend-quality"]["steps"]
    suite = next(step for step in steps if step["name"] == "Python Test Suite")
    upload = next(step for step in steps if step["name"] == "Upload Pytest Report")
    assert "-o junit_logging=all" in suite["run"]
    assert "--junitxml=pytest-results.xml" in suite["run"]
    assert upload["if"] == "always()"
    assert "pytest-results.xml" in upload["with"]["path"]
