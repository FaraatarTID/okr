"""Process-level T23 session-registry drill against the shared database backend.

Two backend processes and two BFF processes share one disposable SQLite file
through ``OKR_BACKEND_SECURITY_STATE_BACKEND=database``. The backend processes
create the registry tables themselves by running the Alembic migrations at startup.
Runs locally when the spa-bff Node dependencies are installed; CI requires it with
``OKR_REQUIRE_T23_PROCESS_DRILL=true``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid
from datetime import datetime, timedelta, timezone

import pytest


pytestmark = pytest.mark.integration

_SERVICE_TOKEN = "t23-process-service-token"
_SIGNING_SECRET = "t23-process-signing-secret-for-tests"
_BFF_SESSION_SECRET = "t23-process-bff-session-secret-at-least-32-chars"
_LOGIN_USERNAME = "t23_session_member"
_LOGIN_PASSWORD = "T23-Process-Password-123!"


def _skip_or_fail_missing_prerequisite(message: str) -> None:
    if os.getenv("OKR_REQUIRE_T23_PROCESS_DRILL", "").strip().lower() == "true":
        pytest.fail(message)
    pytest.skip(message)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    timeout: float = 5,
) -> tuple[int, dict[str, str], bytes]:
    body = raw_body
    if body is None and payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if body is not None:
        request_headers.setdefault("content-type", "application/json")
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as error_response:
        return (
            error_response.code,
            {key.lower(): value for key, value in error_response.headers.items()},
            error_response.read(),
        )
    except URLError as exc:
        raise AssertionError(f"HTTP request to {url!r} failed: {exc.reason}") from exc
    with response:
        normalized_headers = {
            key.lower(): value for key, value in response.headers.items()
        }
        set_cookies = response.headers.get_all("Set-Cookie")
        if set_cookies:
            normalized_headers["set-cookie"] = "\n".join(set_cookies)
        return response.status, normalized_headers, response.read()


def _wait_for_health(
    url: str,
    process: subprocess.Popen[Any],
    *,
    log_path: Path,
    timeout_seconds: float = 45,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"Service exited during startup (code {process.returncode}).\n"
                f"log tail:\n{_safe_log_tail(log_path)}"
            )
        try:
            status, _, _ = _http(url, timeout=5)
            if status == 200:
                return
            last_error = f"health returned HTTP {status}"
        except Exception as exc:  # startup socket is expected to be closed initially
            last_error = str(exc)
        time.sleep(0.2)
    raise AssertionError(
        f"Service did not become healthy: {last_error}\n"
        f"log tail:\n{_safe_log_tail(log_path)}"
    )


def _safe_log_tail(path: Path, *, max_chars: int = 4000) -> str:
    if not path.is_file():
        return ""
    contents = path.read_text(encoding="utf-8", errors="replace")[-max_chars:]
    for secret in (
        _SERVICE_TOKEN,
        _SIGNING_SECRET,
        _BFF_SESSION_SECRET,
    ):
        if secret:
            contents = contents.replace(secret, "<redacted>")
    return contents


def _start_process(
    command: list[str], *, cwd: Path, env: dict[str, str], log_path: Path
) -> subprocess.Popen[Any]:
    log_file = log_path.open("wb")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_file.close()
    return process


def _stop_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _seed_test_user(repo_root: Path, db_url: str, env: dict[str, str]) -> None:
    script = r"""
from datetime import datetime, timezone
from sqlmodel import Session
import src.crud as crud
import src.database as database
from src.models import User, UserRole

database.DATABASE_URL = None
database._engine = None
database._migrations_applied_urls.clear()
database.init_database()
with Session(database.get_engine(), expire_on_commit=False) as session:
    user = User(
        username="t23_session_member",
        password_hash=crud.hash_password("T23-Process-Password-123!"),
        display_name="T23 Process Member",
        role=UserRole.MEMBER,
        is_active=True,
        must_change_password=False,
        password_changed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        token_version=1,
    )
    session.add(user)
    session.commit()
"""
    seed_env = env.copy()
    seed_env["OKR_DATABASE_URL"] = db_url
    seed_env["DATABASE_URL"] = db_url
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=seed_env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Disposable integration database seeding failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _base_backend_env(
    *,
    repo_root: Path,
    db_url: str,
    backend_port: int,
) -> dict[str, str]:
    env = os.environ.copy()
    current_pythonpath = str(env.get("PYTHONPATH", "")).strip()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(repo_root), current_pythonpath) if part
    )
    env.update(
        {
            "OKR_ENV": "development",
            "OKR_DATABASE_URL": db_url,
            "DATABASE_URL": db_url,
            "OKR_ALLOW_NON_SUPABASE_DB": "true",
            "OKR_DATA_ACCESS_MODE": "database",
            "OKR_BACKEND_HOST": "127.0.0.1",
            "OKR_BACKEND_PORT": str(backend_port),
            "OKR_BACKEND_API_WORKERS": "1",
            "OKR_BACKEND_SERVICE_TOKEN": _SERVICE_TOKEN,
            "OKR_BACKEND_ENFORCE_TOKEN": "true",
            "OKR_BACKEND_ENFORCE_REQUEST_SIGNING": "true",
            "OKR_BACKEND_SIGNING_SECRET": _SIGNING_SECRET,
            "OKR_BACKEND_SECURITY_STATE_BACKEND": "database",
            "OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS": "10000",
            "OKR_STRICT_RUNTIME_PREFLIGHT": "false",
            "OKR_ENFORCE_STRONG_PASSWORD_POLICY": "false",
            "ALLOW_EXTERNAL_AI": "false",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def _bff_env(*, backend_port: int, bff_port: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "NODE_ENV": "development",
            "BFF_HOST": "127.0.0.1",
            "BFF_PORT": str(bff_port),
            "BFF_SESSION_SECRET": _BFF_SESSION_SECRET,
            "BFF_SESSION_TTL_SECONDS": "600",
            "BFF_COOKIE_SECURE": "false",
            "BFF_REQUEST_TIMEOUT_MS": "5000",
            "OKR_BACKEND_API_URL": f"http://127.0.0.1:{backend_port}",
            "OKR_BACKEND_SERVICE_TOKEN": _SERVICE_TOKEN,
            "OKR_BACKEND_SIGNING_SECRET": _SIGNING_SECRET,
            "OKR_BACKEND_SIGNING_KEY_ID": "",
        }
    )
    return env


def _cookie_pair(headers: dict[str, str]) -> str:
    raw = headers.get("set-cookie", "")
    pieces = []
    for entry in raw.splitlines():
        first = entry.strip().split(";", 1)[0]
        if first.startswith(("okr_spa_session=", "okr_csrf_token=")):
            pieces.append(first)
    if not any(piece.startswith("okr_spa_session=") for piece in pieces):
        raise AssertionError("BFF login did not issue a session cookie.")
    return "; ".join(pieces)


def _signed_service_headers(path: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = f"t23-{uuid.uuid4().hex}"
    message = "\n".join(
        [
            "POST",
            path,
            timestamp,
            nonce,
            hashlib.sha256(body).hexdigest(),
        ]
    )
    signature = hmac.new(
        _SIGNING_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "x-okr-service-token": _SERVICE_TOKEN,
        "x-okr-timestamp": timestamp,
        "x-okr-nonce": nonce,
        "x-okr-signature": signature,
        "content-type": "application/json",
    }


def _mint_unknown_session_cookie(*, actor: dict[str, Any]) -> str:
    now = int(time.time())
    payload = {
        "v": "v1",
        "iat": now,
        "exp": now + 600,
        "sid": f"unknown-{uuid.uuid4().hex}",
        "user": actor,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode("ascii")
        .rstrip("=")
    )
    signature = hmac.new(
        _BFF_SESSION_SECRET.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    return f"okr_spa_session={payload_b64}.{signature}"


def test_session_registry_processes_share_registration_and_revoke_across_restart(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    bff_root = repo_root / "spa-bff"
    if not (bff_root / "node_modules" / "tsx").exists():
        _skip_or_fail_missing_prerequisite(
            "Install spa-bff Node dependencies to run the process integration drill."
        )

    database_path = tmp_path / "t23-process-integration.sqlite3"
    db_url = f"sqlite:///{database_path.as_posix()}"
    ports: list[int] = []
    while len(ports) < 4:
        candidate = _free_local_port()
        if candidate not in ports:
            ports.append(candidate)
    backend_a_port, backend_b_port, bff_a_port, bff_b_port = ports

    backend_a_env = _base_backend_env(
        repo_root=repo_root,
        db_url=db_url,
        backend_port=backend_a_port,
    )
    backend_b_env = _base_backend_env(
        repo_root=repo_root,
        db_url=db_url,
        backend_port=backend_b_port,
    )
    bff_a_env = _bff_env(backend_port=backend_a_port, bff_port=bff_a_port)
    bff_b_env = _bff_env(backend_port=backend_b_port, bff_port=bff_b_port)
    _seed_test_user(repo_root, db_url, backend_a_env)

    processes: dict[str, subprocess.Popen[Any]] = {}

    def start_backend(name: str, port: int, env: dict[str, str]) -> None:
        process = _start_process(
            [sys.executable, "-m", "backend_app.run_api"],
            cwd=repo_root,
            env=env,
            log_path=tmp_path / f"{name}.log",
        )
        processes[name] = process
        _wait_for_health(
            f"http://127.0.0.1:{port}/healthz",
            process,
            log_path=tmp_path / f"{name}.log",
            timeout_seconds=90,
        )

    def start_bff(name: str, port: int, env: dict[str, str]) -> None:
        process = _start_process(
            ["node", "--import", "tsx/esm", "src/server.ts"],
            cwd=bff_root,
            env=env,
            log_path=tmp_path / f"{name}.log",
        )
        processes[name] = process
        _wait_for_health(
            f"http://127.0.0.1:{port}/healthz",
            process,
            log_path=tmp_path / f"{name}.log",
            timeout_seconds=60,
        )

    try:
        start_backend("backend-a", backend_a_port, backend_a_env)
        start_backend("backend-b", backend_b_port, backend_b_env)
        start_bff("bff-a", bff_a_port, bff_a_env)
        start_bff("bff-b", bff_b_port, bff_b_env)

        login_status, login_headers, login_body = _http(
            f"http://127.0.0.1:{bff_a_port}/session/login",
            method="POST",
            payload={"username": _LOGIN_USERNAME, "password": _LOGIN_PASSWORD},
        )
        assert login_status == 200, login_body.decode("utf-8", errors="replace")
        cookie = _cookie_pair(login_headers)
        login_result = json.loads(login_body)
        user = login_result.get("user")
        assert isinstance(user, dict) and int(user.get("id", 0)) > 0

        second_login_status, second_login_headers, second_login_body = _http(
            f"http://127.0.0.1:{bff_a_port}/session/login",
            method="POST",
            payload={"username": _LOGIN_USERNAME, "password": _LOGIN_PASSWORD},
        )
        assert second_login_status == 200, second_login_body.decode(
            "utf-8", errors="replace"
        )
        second_cookie = _cookie_pair(second_login_headers)
        second_user = json.loads(second_login_body).get("user")
        assert isinstance(second_user, dict)
        assert int(second_user.get("id", 0)) == int(user["id"])

        # Independent backend B must observe two registrations for the same user.
        me_status, _, me_body = _http(
            f"http://127.0.0.1:{bff_b_port}/session/me",
            headers={"cookie": cookie},
        )
        assert me_status == 200, me_body.decode("utf-8", errors="replace")
        second_me_status, _, second_me_body = _http(
            f"http://127.0.0.1:{bff_b_port}/session/me",
            headers={"cookie": second_cookie},
        )
        assert second_me_status == 200, second_me_body.decode("utf-8", errors="replace")

        # Exercise the configured database provider at exp == now and immediately
        # after. Registration goes through the signed backend service endpoint;
        # checks use an independent store client on the same database.
        boundary_session_id = f"expiry-boundary-{uuid.uuid4().hex}"
        boundary_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        register_path = "/v1/internal/session-registry/register"
        register_body = json.dumps(
            {
                "session_id": boundary_session_id,
                "actor_id": int(user["id"]),
                "expires_at": boundary_expiry.isoformat(timespec="microseconds"),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        boundary_status, _, boundary_body = _http(
            f"http://127.0.0.1:{backend_a_port}{register_path}",
            method="POST",
            headers=_signed_service_headers(register_path, register_body),
            raw_body=register_body,
        )
        assert boundary_status == 200, boundary_body.decode("utf-8", errors="replace")
        from backend_app.security_state import DatabaseSecurityStateStore

        boundary_store = DatabaseSecurityStateStore(database_url=db_url)
        try:
            boundary_digest = hashlib.sha256(
                boundary_session_id.encode("utf-8")
            ).hexdigest()
            assert (
                boundary_store.check_session(
                    session_digest=boundary_digest,
                    actor_id=str(user["id"]),
                    now=boundary_expiry,
                )
                == "active"
            )
            assert (
                boundary_store.check_session(
                    session_digest=boundary_digest,
                    actor_id=str(user["id"]),
                    now=boundary_expiry + timedelta(microseconds=1),
                )
                == "unknown"
            )
        finally:
            boundary_store.dispose()

        # A signed cookie absent from the registry is never accepted by backend B.
        unknown_cookie = _mint_unknown_session_cookie(actor=user)
        unknown_status, _, unknown_body = _http(
            f"http://127.0.0.1:{bff_b_port}/session/me",
            headers={"cookie": unknown_cookie},
        )
        assert unknown_status == 401, unknown_body.decode("utf-8", errors="replace")

        # Logout on A must persist before success; recreate both BFF and backend B
        # to prove neither process-local state nor a cached provider connection decides.
        logout_status, _, logout_body = _http(
            f"http://127.0.0.1:{bff_a_port}/session/logout",
            method="POST",
            headers={"cookie": cookie},
        )
        assert logout_status == 200, logout_body.decode("utf-8", errors="replace")

        _stop_process(processes.pop("bff-b", None))
        _stop_process(processes.pop("backend-b", None))
        start_backend("backend-b", backend_b_port, backend_b_env)
        start_bff("bff-b", bff_b_port, bff_b_env)

        revoked_status, _, revoked_body = _http(
            f"http://127.0.0.1:{bff_b_port}/session/me",
            headers={"cookie": cookie},
        )
        assert revoked_status == 401, revoked_body.decode("utf-8", errors="replace")
        still_active_status, _, still_active_body = _http(
            f"http://127.0.0.1:{bff_b_port}/session/me",
            headers={"cookie": second_cookie},
        )
        assert still_active_status == 200, still_active_body.decode(
            "utf-8", errors="replace"
        )

        # Fail closed when the shared registry storage is unusable: drop the
        # migration-owned tables under a freshly started backend B. It must answer
        # 503 (never fall back to process-local state or accept the cookie).
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool

        from tests._security_state_schema import drop_security_state_tables

        _stop_process(processes.pop("bff-b", None))
        _stop_process(processes.pop("backend-b", None))
        outage_engine = create_engine(db_url, poolclass=NullPool)
        try:
            drop_security_state_tables(outage_engine)
        finally:
            outage_engine.dispose()
        start_backend("backend-b-outage", backend_b_port, backend_b_env)
        start_bff("bff-b-outage", bff_b_port, bff_b_env)
        outage_status, _, outage_body = _http(
            f"http://127.0.0.1:{bff_b_port}/session/me",
            headers={"cookie": second_cookie},
        )
        assert outage_status == 503, outage_body.decode("utf-8", errors="replace")
    finally:
        for process in reversed(list(processes.values())):
            _stop_process(process)
