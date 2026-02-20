"""Request security helpers for backend API."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from threading import Lock
from fastapi import Header, HTTPException, Request

from backend_app.config import get_backend_settings
from backend_app.rate_limiter import check_rate_limit


_NONCE_SEEN: dict[str, int] = {}
_NONCE_LOCK = Lock()


def _body_digest_hex(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def _canonical_signing_payload(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_digest: str,
) -> str:
    return "\n".join(
        [
            str(method or "").strip().upper(),
            str(path or "/").strip() or "/",
            str(timestamp or "").strip(),
            str(nonce or "").strip(),
            str(body_digest or "").strip(),
        ]
    )


def _expected_signature(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    secret: str,
) -> str:
    payload = _canonical_signing_payload(
        method=method,
        path=path,
        timestamp=timestamp,
        nonce=nonce,
        body_digest=_body_digest_hex(body),
    )
    return hmac.new(
        str(secret).encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _prune_nonce_cache(now_ts: int, window_seconds: int) -> None:
    cutoff = int(now_ts) - int(window_seconds)
    stale = [key for key, seen_at in _NONCE_SEEN.items() if int(seen_at) < cutoff]
    for key in stale:
        _NONCE_SEEN.pop(key, None)


def _register_nonce_or_reject(*, nonce: str, now_ts: int, window_seconds: int) -> None:
    with _NONCE_LOCK:
        _prune_nonce_cache(now_ts, window_seconds)
        seen_at = _NONCE_SEEN.get(nonce)
        if seen_at is not None and int(seen_at) >= int(now_ts) - int(window_seconds):
            raise HTTPException(status_code=401, detail="Replay request rejected.")
        _NONCE_SEEN[nonce] = int(now_ts)


async def _verify_request_signature(
    *,
    request: Request,
    supplied_signature: str | None,
    supplied_timestamp: str | None,
    supplied_nonce: str | None,
) -> None:
    settings = get_backend_settings()
    secret = settings.signing_secret
    if not secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Backend request-signing enforcement is enabled but "
                "OKR_BACKEND_SIGNING_SECRET is not configured."
            ),
        )

    signature = str(supplied_signature or "").strip().lower()
    timestamp_raw = str(supplied_timestamp or "").strip()
    nonce = str(supplied_nonce or "").strip()
    if not signature or not timestamp_raw or not nonce:
        raise HTTPException(status_code=401, detail="Missing signed request headers.")

    try:
        timestamp_int = int(timestamp_raw)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid request timestamp.") from exc

    now_ts = int(time.time())
    if abs(now_ts - timestamp_int) > int(settings.request_signing_window_seconds):
        raise HTTPException(status_code=401, detail="Request signature expired.")

    body = await request.body()
    expected = _expected_signature(
        method=request.method,
        path=str(request.url.path or "/"),
        timestamp=timestamp_raw,
        nonce=nonce,
        body=body,
        secret=secret,
    )
    if not secrets.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid request signature.")

    _register_nonce_or_reject(
        nonce=nonce,
        now_ts=now_ts,
        window_seconds=settings.request_signing_window_seconds,
    )


async def require_service_access(
    request: Request,
    x_okr_service_token: str | None = Header(default=None),
    x_okr_signature: str | None = Header(default=None),
    x_okr_timestamp: str | None = Header(default=None),
    x_okr_nonce: str | None = Header(default=None),
) -> None:
    settings = get_backend_settings()
    if settings.enforce_service_token:
        expected = settings.service_token
        if not expected:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Backend service token enforcement is enabled but "
                    "OKR_BACKEND_SERVICE_TOKEN is not configured."
                ),
            )
        supplied = str(x_okr_service_token or "").strip()
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="Unauthorized service token.")

    if settings.enforce_request_signing:
        await _verify_request_signature(
            request=request,
            supplied_signature=x_okr_signature,
            supplied_timestamp=x_okr_timestamp,
            supplied_nonce=x_okr_nonce,
        )

    # Rate limit by client IP regardless of token mode.
    client_ip = request.client.host if request.client else "unknown"
    rl_ok = check_rate_limit(
        key=f"ip:{client_ip}",
        limit=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not rl_ok:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")


def resolve_actor_username(
    *,
    header_actor: str | None,
    payload_actor: str | None,
) -> str:
    actor = str(header_actor or payload_actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="Actor username is required.")
    if len(actor) > 128:
        raise HTTPException(status_code=400, detail="Actor username is too long.")
    return actor
