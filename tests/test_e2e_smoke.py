from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener

import pytest


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_response(response) -> dict:
    body = response.read().decode("utf-8").strip()
    if not body:
        return {}
    return json.loads(body)


def _request_json(
    client: OpenerDirector,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
) -> tuple[int, dict]:
    request_headers = {"accept": "application/json"}
    if headers:
        request_headers.update(headers)

    request_body = None
    if payload is not None:
        request_headers["content-type"] = "application/json"
        request_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )

    request = Request(url=url, data=request_body, headers=request_headers, method=method)
    with client.open(request, timeout=25) as response:
        return int(response.status), _parse_response(response)


def _wait_for_ok(client: OpenerDirector, *, url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with client.open(Request(url=url, method="GET"), timeout=4) as response:
                if 200 <= int(response.status) < 500:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def _read_cookie_value(jar: CookieJar, *, name: str) -> str:
    for cookie in jar:
        if cookie.name == name:
            return str(cookie.value)
    return ""


def _csrf_token_from_cookie(jar: CookieJar) -> str:
    return _read_cookie_value(jar, name="okr_csrf_token")


def _read_with_retry(
    client: OpenerDirector,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[int, dict]:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return _request_json(
                client,
                method=method,
                url=url,
                headers=headers,
                payload=payload,
            )
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.75)
    if last_error is not None:
        raise RuntimeError(f"Request failed for {url}: {last_error}")
    raise RuntimeError(f"Request failed for {url}.")


@dataclass(frozen=True)
class _SmokeConfig:
    bff_url: str
    web_url: str


@pytest.fixture(scope="module")
def smoke_env() -> _SmokeConfig:
    if not _truthy(os.getenv("TOP10_SMOKE")):
        pytest.skip("Smoke test disabled. Set TOP10_SMOKE=1 to run.")

    bff_url = os.getenv("TOP10_SMOKE_BFF_URL", "").strip()
    web_url = os.getenv("TOP10_SMOKE_WEB_URL", "").strip()
    if not bff_url or not web_url:
        pytest.fail("Missing TOP10_SMOKE_BFF_URL or TOP10_SMOKE_WEB_URL.")

    if not (bff_url.startswith("http://") or bff_url.startswith("https://")):
        pytest.fail("TOP10_SMOKE_BFF_URL must be a valid URL.")
    if not (web_url.startswith("http://") or web_url.startswith("https://")):
        pytest.fail("TOP10_SMOKE_WEB_URL must be a valid URL.")

    return _SmokeConfig(bff_url=bff_url.rstrip("/"), web_url=web_url.rstrip("/"))


def _do_login(client: OpenerDirector, *, bff_url: str) -> str:
    status, payload = _request_json(
        client,
        method="POST",
        url=f"{bff_url}/session/login",
        payload={"username": "admin", "password": "admin", "client_ip": "127.0.0.1"},
    )
    if status != 200:
        raise RuntimeError(f"Login request failed with status {status}: {payload}")
    if not bool(payload.get("success")):
        raise RuntimeError(f"Login response indicates authentication failure: {payload}")

    me_status, me_payload = _read_with_retry(
        client,
        method="GET",
        url=f"{bff_url}/session/me",
        timeout_seconds=15,
    )
    if me_status != 200:
        raise RuntimeError(f"Session validation failed with status {me_status}: {me_payload}")

    actor = str((me_payload.get("user") or {}).get("username") or "").strip()
    if not actor:
        raise RuntimeError(f"session/me did not return a username: {me_payload}")
    return actor


def _run_read_query(
    client: OpenerDirector,
    *,
    bff_url: str,
    actor: str,
) -> dict:
    status, payload = _request_json(
        client,
        method="POST",
        url=f"{bff_url}/api/backend/read/query",
        headers={"x-okr-actor": actor},
        payload={
            "kind": "users.by_username",
            "params": {"username": actor},
            "actor_username": actor,
        },
    )
    if status != 200:
        raise RuntimeError(f"Read query returned status {status}: {payload}")
    if "user" not in payload:
        raise RuntimeError(f"Read query payload missing user field: {payload}")
    return payload


def _run_job_smoke(
    client: OpenerDirector,
    *,
    bff_url: str,
    actor: str,
    csrf_token: str,
) -> dict:
    status, payload = _request_json(
        client,
        method="POST",
        url=f"{bff_url}/api/backend/jobs",
        headers={"x-okr-actor": actor, "x-xsrf-token": csrf_token},
        payload={"kind": "ai.generate_json", "payload": {"prompt": "smoke test"}},
    )
    if status != 202:
        raise RuntimeError(f"Job submit returned status {status}: {payload}")

    job_id = str(payload.get("id") or "").strip()
    if not job_id:
        raise RuntimeError(f"Job payload missing id: {payload}")

    deadline = time.time() + 30
    terminal_status = {"succeeded", "failed", "cancelled"}
    last_payload: dict = {}
    while time.time() < deadline:
        poll_status, poll_payload = _request_json(
            client,
            method="GET",
            url=f"{bff_url}/api/backend/jobs/{job_id}",
            headers={"x-okr-actor": actor},
        )
        if poll_status != 200:
            raise RuntimeError(
                f"Job poll returned status {poll_status} for {job_id}: {poll_payload}"
            )
        if not isinstance(poll_payload, dict):
            raise RuntimeError(f"Job poll payload malformed: {poll_payload}")
        last_payload = poll_payload
        job_state = str(poll_payload.get("status") or "").strip().lower()
        if job_state in terminal_status:
            break
        if job_state in {"pending", "running"}:
            time.sleep(1)
            continue
        raise RuntimeError(
            f"Unexpected job state '{job_state}' for {job_id}: {poll_payload}"
        )
    else:
        raise RuntimeError(
            f"Job {job_id} did not reach terminal/persisting state in time: {last_payload}"
        )

    if str(last_payload.get("id") or "").strip() != job_id:
        raise RuntimeError(f"Job poll mismatch: expected {job_id}, got {last_payload}")

    return last_payload


def test_full_stack_smoke(smoke_env: _SmokeConfig) -> None:
    bff_url = smoke_env.bff_url
    web_url = smoke_env.web_url

    cookie_jar = CookieJar()
    client = build_opener(HTTPCookieProcessor(cookie_jar))

    if not _wait_for_ok(client, url=f"{bff_url}/healthz", timeout_seconds=40):
        raise RuntimeError(f"BFF health endpoint did not become ready: {bff_url}/healthz")
    if not _wait_for_ok(client, url=f"{web_url}", timeout_seconds=40):
        raise RuntimeError(f"Web service did not become ready: {web_url}")

    actor = _do_login(client, bff_url=bff_url)

    read_payload = _run_read_query(client, bff_url=bff_url, actor=actor)
    if not isinstance(read_payload.get("user"), dict):
        raise RuntimeError(f"Invalid read payload: {read_payload}")

    csrf_token = _csrf_token_from_cookie(cookie_jar)
    if not csrf_token:
        raise RuntimeError("CSRF cookie missing after login. Cannot test state-changing route.")

    job_payload = _run_job_smoke(
        client,
        bff_url=bff_url,
        actor=actor,
        csrf_token=csrf_token,
    )
    if not job_payload.get("kind"):
        raise RuntimeError(f"Job payload missing kind: {job_payload}")
