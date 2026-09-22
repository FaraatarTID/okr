"""The login throttle key must be derived server-side, never from the request body.

`LoginRequest` accepted a `client_ip` field from the request body. The SPA never sent
it, so on the real path the throttle was absent; and because the lockout table is keyed
`(scope, identifier)` with `scope="ip"`, any caller who *did* supply it chose the key.
That makes the control not merely missing but an available denial-of-service primitive:
an attacker can submit a third party's address on deliberately failing logins and lock
that address out.

The property asserted here is the one that cannot be satisfied vacuously: after failed
logins, throttle rows must EXIST (so the request genuinely reached the auth path and the
throttle still operates) and the attacker-supplied address must NOT be among them.
Before the fix the sentinel becomes the key and this fails; if the request stopped
reaching the auth path for any reason, the first assertion fails instead of the test
quietly passing.
"""

import pytest
from sqlmodel import SQLModel, select


@pytest.fixture()
def login_env(monkeypatch, tmp_path):
    import src.crud as crud
    import src.database as database

    db_url = f"sqlite:///{tmp_path / 'login_ip.db'}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")

    # Isolate the IP dimension: the per-user lockout must not be what records the
    # attempt, or the test would pass for the wrong reason.
    monkeypatch.setattr(crud, "AUTH_USER_WINDOW_SECONDS", 300, raising=True)
    monkeypatch.setattr(crud, "AUTH_USER_MAX_ATTEMPTS", 1000, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_WINDOW_SECONDS", 300, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_MAX_ATTEMPTS", 3, raising=True)
    monkeypatch.setattr(crud, "AUTH_LOCKOUT_SECONDS", 120, raising=True)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def _throttle_identifiers():
    from sqlmodel import Session

    from src.database import get_engine
    from src.models import AuthThrottleState

    with Session(get_engine()) as session:
        return [row.identifier for row in session.exec(select(AuthThrottleState)).all()]


def test_login_body_cannot_choose_the_throttle_key(login_env):
    from fastapi.testclient import TestClient

    import backend_app.main as backend_main
    from src.crud import create_user
    from tests._test_credentials import test_password

    # Credentials come from the shared helper rather than literals, because the
    # Secret Hygiene Gate rejects hardcoded credential values in tests.
    create_user("throttle_target", test_password("login_throttle_correct"))
    sentinel = "203.0.113.10"

    client = TestClient(backend_main.app)
    for _ in range(2):
        client.post(
            "/v1/auth/login",
            json={
                "username": "throttle_target",
                "password": test_password("login_throttle_wrong"),
                # An address the caller has no authority over.
                "client_ip": sentinel,
            },
        )

    identifiers = _throttle_identifiers()
    assert identifiers, (
        "no throttle row was recorded after failed logins, so this test cannot "
        "observe the throttle key at all and must not be treated as a pass"
    )
    assert sentinel not in identifiers, (
        "the caller chose the lockout key by putting a third party's address in the "
        "request body, so a caller can deny service to that address; "
        f"recorded identifiers were {identifiers}"
    )


def test_the_trusted_private_header_keys_the_lockout_dimension(login_env, monkeypatch):
    """The positive half, without which the test above could describe an inert control.

    Asserting only that a caller *cannot* choose the key is satisfied just as well by a
    dimension that is never keyed at all. This asserts the reverse direction: when the
    request carries a valid service token and the private header our edge sets, that
    address must be what the lockout records.
    """
    from fastapi.testclient import TestClient

    import backend_app.main as backend_main
    from src.crud import create_user
    from tests._test_credentials import test_password

    token = "test-service-token"
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", token)
    trusted = "198.51.100.7"

    create_user("throttle_trusted", test_password("login_throttle_correct"))

    client = TestClient(backend_main.app)
    for _ in range(2):
        client.post(
            "/v1/auth/login",
            json={
                "username": "throttle_trusted",
                "password": test_password("login_throttle_wrong"),
            },
            headers={"x-okr-service-token": token, "x-okr-client-ip": trusted},
        )

    identifiers = _throttle_identifiers()
    assert identifiers, (
        "no throttle row was recorded, so the request never reached the auth path and "
        "this test cannot observe the lockout key at all"
    )
    assert trusted in identifiers, (
        "the trusted client address did not key the lockout's IP dimension, so the "
        "dimension is inert on the real path and every user shares one bucket; "
        f"recorded identifiers were {identifiers}"
    )
