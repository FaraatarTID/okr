"""An account change takes effect on the very next request. Pinned so no cache can weaken it.

A short-TTL cache of the actor scope keyed by (actor, token_version) was proposed and
rejected (docs/REMAINING_ENGINEERING_PLAN.md, P4.3). The key would use the version the CALLER
supplies from its session cookie, so after an account bump the old session would still hit its
own cache entry and be accepted until the TTL expired; and deactivation, demotion and manager
changes never bump the version at all. These tests drive the real dependency through HTTP, with
no monkeypatched scope resolver, so any process-level cache of scope fails them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests import _test_credentials

QUERY = "/v1/read/query"
BODY = {"kind": "cycles.all", "params": {}}


@pytest.fixture()
def member(isolated_db, monkeypatch):
    import backend_app.main as backend_main
    from backend_app import security
    from src.crud import create_user
    from tests.session_registry_test_support import attach_registered_test_session

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_PREAUTH_RATE_LIMIT_MAX_REQUESTS", "10000")
    security._reset_security_state_for_tests()
    user = create_user("fresh_member", _test_credentials.test_password("scope_fresh"))
    client = TestClient(backend_main.app)
    client.headers.update({"x-okr-token-version": "1"})
    attach_registered_test_session(client, actor_id=user.id)
    return client, isolated_db


def _read(client: TestClient) -> int:
    return client.post(
        QUERY, headers={"X-OKR-Actor": "fresh_member"}, json=BODY
    ).status_code


def _edit(engine, **changes) -> None:
    from src.models import User

    with Session(engine) as session:
        row = session.exec(select(User).where(User.username == "fresh_member")).one()
        for name, value in changes.items():
            setattr(row, name, value)
        session.add(row)
        session.commit()


def test_a_request_is_admitted_before_any_change(member):
    client, _ = member
    assert _read(client) == 200, (
        "positive control: without it the tests below prove nothing"
    )
    assert _read(client) == 200


def test_a_token_version_bump_rejects_the_old_session_on_the_next_request(member):
    client, engine = member
    assert _read(client) == 200
    _edit(engine, token_version=2)
    assert _read(client) == 401


def test_deactivating_the_account_takes_effect_on_the_next_request(member):
    client, engine = member
    assert _read(client) == 200
    _edit(engine, is_active=False)
    assert _read(client) == 403


def test_reactivating_the_account_takes_effect_on_the_next_request(member):
    client, engine = member
    _edit(engine, is_active=False)
    assert _read(client) == 403
    _edit(engine, is_active=True)
    assert _read(client) == 200
