"""Request-body ceilings enforced before the body is buffered.

FastAPI reads and parses a JSON body before it runs route dependencies, including the
service-token check, so a size check written inside a handler runs only after the whole
body is already in memory, and only if the client declared a truthful ``Content-Length``.
A chunked upload declares none. This wrapper sits in front of the application and
counts the bytes as they arrive, so it holds for both cases.

It answers 413 itself instead of raising from ``receive``. FastAPI's body reader turns
any exception raised there into a generic 400 ("error parsing the body"), so an exception
never becomes a 413. Two paths, both leaving the handler unrun:

* a declared ``Content-Length`` over the ceiling is refused without calling the app at all;
* a body that crosses the ceiling while streaming is cut off with ``http.disconnect``,
  which stops the app's read before any handler runs, and the response it then produces is
  replaced with the 413.
"""

from __future__ import annotations

import json
from typing import Mapping

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The whole-database restore is the only backend route that legitimately carries a large
# body. Keep this equal to DB_RESTORE_BODY_LIMIT_BYTES in spa-bff/src/server.ts, which
# bounds the same path at the browser edge.
DB_RESTORE_BODY_LIMIT_BYTES = 50 * 1024 * 1024

DEFAULT_ROUTE_BODY_LIMITS: Mapping[tuple[str, str], int] = {
    ("POST", "/v1/admin/db-restore"): DB_RESTORE_BODY_LIMIT_BYTES,
}


def _message(limit_bytes: int) -> str:
    megabytes = limit_bytes / (1024 * 1024)
    label = f"{megabytes:g} MB" if megabytes >= 1 else f"{limit_bytes} bytes"
    return f"Request body too large. Maximum {label}."


def _payload(limit_bytes: int) -> bytes:
    # Same keys as the application's own error envelope, so a client parsing errors does
    # not need a special case for this one.
    text = _message(limit_bytes)
    return json.dumps(
        {"code": "HTTP_413", "error": text, "message": text, "detail": text}
    ).encode("utf-8")


async def _send_413(send: Send, limit_bytes: int) -> None:
    body = _payload(limit_bytes)
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                # The unread remainder of the request body is not going to be consumed.
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class RouteBodyLimitMiddleware:
    """Refuse an over-limit body on the listed ``(method, path)`` routes.

    Routes not listed are untouched, on purpose: this app has not had its other routes'
    body sizes measured, so a blanket ceiling would be a guess.
    """

    def __init__(
        self,
        app: ASGIApp,
        limits: Mapping[tuple[str, str], int] | None = None,
    ) -> None:
        self.app = app
        self.limits = dict(DEFAULT_ROUTE_BODY_LIMITS if limits is None else limits)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limits.get((str(scope["method"]).upper(), scope["path"]))
        if limit is None:
            await self.app(scope, receive, send)
            return

        declared = self._declared_length(scope)
        if declared is not None and declared > limit:
            await _send_413(send, limit)
            return

        received = 0
        exceeded = False
        replaced = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                # Counted here, not trusted from the header: a chunked upload has no
                # Content-Length, and a lying one can understate the body.
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal replaced
            if not exceeded:
                await send(message)
                return
            # The app's own answer to a cut-off body (a 400) is replaced once, and the
            # rest of what it sends is dropped.
            if not replaced:
                replaced = True
                await _send_413(send, limit)

        await self.app(scope, limited_receive, guarded_send)

    @staticmethod
    def _declared_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    # An unparseable value is not evidence of a small body. Fall back to
                    # counting bytes rather than trusting or rejecting it here.
                    return None
                return length if length >= 0 else None
        return None


__all__ = [
    "DB_RESTORE_BODY_LIMIT_BYTES",
    "DEFAULT_ROUTE_BODY_LIMITS",
    "RouteBodyLimitMiddleware",
]
