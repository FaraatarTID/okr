"""The restore body ceiling must hold before the body is buffered.

The handler-level `Content-Length` check this replaces bounded nothing: FastAPI parses
the body before it runs dependencies, and a chunked upload carries no header to check.
These tests prove the purpose (memory is not consumed and the handler never runs), not
just that a header comparison returns 413.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend_app.body_limit import (
    DB_RESTORE_BODY_LIMIT_BYTES,
    DEFAULT_ROUTE_BODY_LIMITS,
    RouteBodyLimitMiddleware,
)

LIMIT = 1024
PATH = "/v1/admin/db-restore"


class Payload(BaseModel):
    format: str


def _app(events: list[str], *, limits=None) -> FastAPI:
    app = FastAPI()

    def deny() -> None:
        events.append("dependency")
        raise HTTPException(status_code=401, detail="no token")

    @app.post(PATH, dependencies=[Depends(deny)])
    async def restore(request: Request, payload: Payload) -> dict:
        events.append("handler")
        return {"ok": True}

    @app.post("/v1/other")
    async def other(payload: Payload) -> dict:
        events.append("other-handler")
        return {"ok": True}

    app.add_middleware(
        RouteBodyLimitMiddleware,
        limits={("POST", PATH): LIMIT} if limits is None else limits,
    )
    return app


def _chunks(total: int, size: int = 256):
    sent = 0
    while sent < total:
        piece = min(size, total - sent)
        sent += piece
        yield b"a" * piece


def _json_of_size(total: int) -> bytes:
    prefix = b'{"format":"'
    suffix = b'"}'
    return prefix + b"a" * max(0, total - len(prefix) - len(suffix)) + suffix


def test_the_production_limit_is_pinned_and_covers_only_restore():
    assert DB_RESTORE_BODY_LIMIT_BYTES == 50 * 1024 * 1024
    assert DEFAULT_ROUTE_BODY_LIMITS == {("POST", PATH): DB_RESTORE_BODY_LIMIT_BYTES}


def test_a_body_under_the_limit_reaches_the_route():
    events: list[str] = []
    client = TestClient(_app(events))

    response = client.post(PATH, content=_json_of_size(LIMIT // 2))

    # Positive control: without it, every refusal below would pass just as well if the
    # middleware rejected all requests.
    assert response.status_code == 401
    assert events == ["dependency"]


def test_an_honest_oversize_content_length_is_refused_before_the_route_runs():
    events: list[str] = []
    client = TestClient(_app(events))

    response = client.post(PATH, content=_json_of_size(LIMIT * 4))

    assert response.status_code == 413
    assert "too large" in str(response.json().get("detail", "")).lower()
    assert events == []


def test_a_chunked_upload_with_no_content_length_is_refused_on_bytes_received():
    events: list[str] = []
    client = TestClient(_app(events))

    # A generator body is sent chunked, so there is no Content-Length to compare. This is
    # the case the old handler-level check could not see at all.
    response = client.post(PATH, content=_chunks(LIMIT * 4))

    assert response.status_code == 413
    assert events == []


def test_a_chunked_upload_at_or_under_the_limit_is_not_refused():
    events: list[str] = []
    client = TestClient(_app(events))

    response = client.post(PATH, content=_chunks(LIMIT))

    assert response.status_code != 413
    assert events == ["dependency"]


def test_an_understated_content_length_does_not_smuggle_a_large_body():
    events: list[str] = []
    app = _app(events)
    sent: list[dict] = []
    body = _json_of_size(LIMIT * 4)

    async def drive() -> None:
        messages = [
            {"type": "http.request", "body": body[: LIMIT * 2], "more_body": True},
            {"type": "http.request", "body": body[LIMIT * 2 :], "more_body": False},
        ]

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": PATH,
            "raw_path": PATH.encode(),
            "query_string": b"",
            "root_path": "",
            # Declares 10 bytes while sending 4 KiB.
            "headers": [
                (b"content-length", b"10"),
                (b"content-type", b"application/json"),
            ],
            "server": ("test", 80),
            "client": ("127.0.0.1", 1),
        }
        await app(scope, receive, send)

    import asyncio

    asyncio.run(drive())

    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 413
    assert events == []


def test_other_routes_are_not_limited():
    events: list[str] = []
    client = TestClient(_app(events))

    response = client.post(
        "/v1/other",
        content=_json_of_size(LIMIT * 8),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert events == ["other-handler"]


def test_only_the_listed_method_is_limited():
    events: list[str] = []
    client = TestClient(_app(events))

    # GET on the restore path is a different route (405), not a body-limited one; the
    # point is that the limiter keys on method as well as path.
    response = client.request("GET", PATH, content=_json_of_size(LIMIT * 4))

    assert response.status_code == 405
    assert events == []


def test_the_real_app_refuses_an_oversize_restore_before_authenticating(monkeypatch):
    # Wiring test against the actual application, not the stand-in above: proves the
    # middleware is installed on the app that ships, and sits in front of the service
    # token check (no token is sent here, and the answer is 413, not 401).
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    client = TestClient(backend_main.app)

    response = client.post(
        PATH,
        content=_chunks(DB_RESTORE_BODY_LIMIT_BYTES + 1024, size=1024 * 1024),
    )

    assert response.status_code == 413
