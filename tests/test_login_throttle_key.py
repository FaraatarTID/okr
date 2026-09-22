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


def _throttle_rows():
    """The recorded `(scope, identifier)` pairs.

    The scope matters as much as the identifier here: "no IP bucket was created" and
    "an IP bucket was created under a name the caller chose" are different failures, and
    a list of identifiers alone cannot tell them apart.
    """
    from sqlmodel import Session

    from src.database import get_engine
    from src.models import AuthThrottleState

    with Session(get_engine()) as session:
        return [
            (str(row.scope), str(row.identifier))
            for row in session.exec(select(AuthThrottleState)).all()
        ]


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


def test_caller_supplied_forwarding_headers_cannot_choose_the_lockout_key(
    login_env, monkeypatch
):
    """X-Forwarded-For and X-Real-IP must not become the lockout's IP identifier.

    The rejection case and its valid control are the same request, deliberately. The
    request carries the trusted private header our edge sets, so an IP bucket IS created
    and the question is not whether the dimension fires but which address it records. A
    test that omitted the trusted header would pass for the wrong reason, because with no
    verified address nothing is keyed at all and every forbidden source is trivially
    absent from the recorded rows.
    """
    from fastapi.testclient import TestClient

    import backend_app.main as backend_main
    from src.crud import create_user
    from tests._test_credentials import test_password

    token = "test-service-token"
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", token)

    trusted = "198.51.100.7"
    forwarded_for_sentinel = "203.0.113.10"
    real_ip_sentinel = "203.0.113.11"

    create_user("throttle_headers", test_password("login_throttle_correct"))

    client = TestClient(backend_main.app)
    for _ in range(2):
        client.post(
            "/v1/auth/login",
            json={
                "username": "throttle_headers",
                "password": test_password("login_throttle_wrong"),
            },
            headers={
                "x-okr-service-token": token,
                "x-okr-client-ip": trusted,
                # `deploy/nginx.conf` builds X-Forwarded-For with
                # `$proxy_add_x_forwarded_for`, which appends to the client-supplied
                # chain, so its leftmost entry is caller-controlled. X-Real-IP is
                # overwritten at the edge, but the backend must not read either one.
                "x-forwarded-for": forwarded_for_sentinel,
                "x-real-ip": real_ip_sentinel,
            },
        )

    rows = _throttle_rows()
    assert rows, (
        "no throttle row was recorded, so the request never reached the auth path and "
        "this test cannot observe the lockout key at all"
    )
    identifiers = [identifier for _scope, identifier in rows]
    assert trusted in identifiers, (
        "the valid control failed: the trusted private header did not key the IP "
        "dimension on this request, so the rejections below would be vacuous; "
        f"recorded rows were {rows}"
    )
    for sentinel, header in (
        (forwarded_for_sentinel, "X-Forwarded-For"),
        (real_ip_sentinel, "X-Real-IP"),
    ):
        assert sentinel not in identifiers, (
            f"a caller-supplied {header} became a lockout identifier, so a caller can "
            "lock out any address it names; "
            f"recorded rows were {rows}"
        )


@pytest.mark.parametrize(
    "header_name",
    ["x-forwarded-for", "x-real-ip"],
    ids=["forwarded-for", "real-ip"],
)
def test_a_forwarding_header_alone_cannot_create_an_ip_bucket(
    login_env, monkeypatch, header_name
):
    """Neither forwarding header may stand in for the absent private header.

    The precedence test above sends the private header and proves which address wins. It
    cannot detect a fallback consulted ONLY in that header's absence, which is the shape
    an unauthorized fallback actually takes, so this case sends one forwarding header and
    no private header at all.

    A valid service token is supplied so the request is authenticated as originating from
    the BFF and the trusted branch is genuinely reachable: an inert dimension must be the
    result of the missing private header, not of the branch never running. Both halves are
    asserted, because an unreached auth path also produces no IP bucket.
    """
    from fastapi.testclient import TestClient

    import backend_app.main as backend_main
    from src.crud import create_user
    from tests._test_credentials import test_password

    token = "test-service-token"
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", token)

    sentinel = "203.0.113.10"
    create_user("throttle_alone", test_password("login_throttle_correct"))

    client = TestClient(backend_main.app)
    for _ in range(2):
        client.post(
            "/v1/auth/login",
            json={
                "username": "throttle_alone",
                "password": test_password("login_throttle_wrong"),
            },
            headers={"x-okr-service-token": token, header_name: sentinel},
        )

    rows = _throttle_rows()
    assert rows, (
        "no throttle row was recorded, so the request never reached the auth path and "
        "this test cannot observe anything"
    )
    assert ("user", "throttle_alone") in rows, (
        "the account dimension did not record the attempt, so the absence of an IP "
        f"bucket below would be indistinguishable from an unreached auth path; got {rows}"
    )
    assert "ip" not in {scope for scope, _identifier in rows}, (
        f"a lone {header_name} header created an IP lockout bucket, so it is being "
        "honoured as a fallback for the absent private header and a caller can lock out "
        f"an address it names; recorded rows were {rows}"
    )


def test_without_a_trusted_client_ip_no_ip_bucket_exists_and_the_account_still_locks(
    login_env, monkeypatch
):
    """The IP dimension's inert failure direction, and that the account dimension survives it.

    Neither a body field nor a forwarding header is authoritative, so with no verified
    client address no `ip` row may exist at all. That is only an acceptable failure
    direction because the per-username dimension still applies, so this asserts both
    halves - the absence, and enforcement at the configured threshold rather than the
    mere existence of a record.

    The thresholds are set so the two dimensions cannot be confused: the IP limit is
    LOWER than the user limit, so if an IP bucket were created it would lock first and
    change the observed error codes. Asserting only that some throttle row exists would
    pass in both worlds.
    """
    import src.crud as crud
    from fastapi.testclient import TestClient

    import backend_app.main as backend_main
    from src.crud import create_user
    from tests._test_credentials import test_password

    monkeypatch.setattr(crud, "AUTH_USER_MAX_ATTEMPTS", 3, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_MAX_ATTEMPTS", 2, raising=True)

    create_user("throttle_noip", test_password("login_throttle_correct"))

    sentinel = "203.0.113.99"
    client = TestClient(backend_main.app)

    error_codes = []
    for _ in range(3):
        response = client.post(
            "/v1/auth/login",
            json={
                "username": "throttle_noip",
                "password": test_password("login_throttle_wrong"),
            },
            # Deliberately present and deliberately not authoritative.
            headers={"x-forwarded-for": sentinel, "x-real-ip": sentinel},
        )
        error_codes.append(response.json().get("error_code"))

    rows = _throttle_rows()
    scopes = {scope for scope, _identifier in rows}
    assert "ip" not in scopes, (
        "an IP lockout bucket was created even though no trusted client address was "
        f"available, so the dimension is not inert; recorded rows were {rows}"
    )
    assert ("user", "throttle_noip") in rows, (
        "the account dimension did not record the failed attempts, so with no trusted "
        "client address no lockout would exist at all and the account could be brute "
        f"forced; recorded rows were {rows}"
    )

    # Enforcement, at the configured threshold. An IP bucket would have locked on the
    # second attempt, so these codes are themselves evidence about which dimension fired.
    assert error_codes[:2] == ["AUTH_INVALID_CREDENTIALS"] * 2, (
        "the account locked earlier than its configured threshold, so the recorded "
        f"attempts are not what is being enforced; got {error_codes}"
    )
    assert error_codes[2] == "AUTH_LOCKED_USER", (
        "the third failed attempt did not lock the account, so the username dimension "
        f"is recorded but not enforced; got {error_codes}"
    )

    still_locked = client.post(
        "/v1/auth/login",
        json={
            "username": "throttle_noip",
            "password": test_password("login_throttle_correct"),
        },
        headers={"x-forwarded-for": sentinel, "x-real-ip": sentinel},
    )
    assert still_locked.json().get("error_code") == "AUTH_LOCKED_USER", (
        "the correct password was accepted while the account was locked, so the lock is "
        "not enforced on the real path"
    )
