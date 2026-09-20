from __future__ import annotations

import pytest
from sqlmodel import Session, select

from scripts import seed_dev_demo
from tests._test_credentials import credential_password


def _environment(database_url: str) -> dict[str, str]:
    return {
        "OKR_DEV_DISPOSABLE": "1",
        "OKR_ENV": "development",
        "OKR_SAAS_MODE": "false",
        "OKR_DEPLOYMENT_PROFILE": "on_premise",
        "OKR_DATA_ACCESS_MODE": "database",
        "OKR_DATABASE_URL": database_url,
    }


def test_seed_requires_explicit_confirmation() -> None:
    with pytest.raises(seed_dev_demo.SeedConfigError, match="confirm-disposable"):
        seed_dev_demo.validate_request(
            argv=[], environ=_environment("sqlite:///tmp.db")
        )


def test_seed_rejects_saas_mode() -> None:
    environment = _environment("sqlite:///tmp.db")
    environment["OKR_SAAS_MODE"] = "true"

    with pytest.raises(seed_dev_demo.SeedConfigError, match="SaaS"):
        seed_dev_demo.validate_request(
            argv=["--confirm-disposable"], environ=environment
        )


def test_seed_is_idempotent_and_creates_minimal_hierarchy(isolated_db) -> None:
    password = credential_password("dev-demo-admin")
    first = seed_dev_demo.seed_demo(
        isolated_db,
        password=password,
        reset_admin_password=True,
    )
    second = seed_dev_demo.seed_demo(
        isolated_db,
        password=password,
    )

    assert first["created"] == {
        "admin": 1,
        "team": 1,
        "cycle": 1,
        "goal": 1,
        "objective": 1,
        "key_result": 2,
        "task": 1,
    }
    assert all(value == 0 for value in second["created"].values())
    with Session(isolated_db) as session:
        assert len(session.exec(select(seed_dev_demo.User)).all()) == 1
        assert len(session.exec(select(seed_dev_demo.KeyResult)).all()) == 2
        assert len(session.exec(select(seed_dev_demo.Task)).all()) == 1


def test_seed_rejects_production_like_environment() -> None:
    environment = _environment("postgresql+psycopg2://okr@postgres/okr")
    environment["OKR_ENV"] = "production"

    with pytest.raises(seed_dev_demo.SeedConfigError, match="production-like"):
        seed_dev_demo.validate_request(
            argv=["--confirm-disposable"], environ=environment
        )
