"""Request security helpers for backend API."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from fastapi import Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from backend_app.config import get_backend_settings
from backend_app.rate_limiter import check_rate_limit
from backend_app.security_state import (
    SecurityStateUnavailableError,
    check_session,
    register_nonce_once,
    reset_security_state_for_tests,
)
from src.utils.crypto_utils import body_digest_hex, canonical_signing_payload


def _expected_signature(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    secret: str,
    session_id: str | None = None,
    session_actor: str | None = None,
) -> str:
    payload = canonical_signing_payload(
        method=method,
        path=path,
        timestamp=timestamp,
        nonce=nonce,
        body_digest=body_digest_hex(body),
        session_id=session_id,
        session_actor=session_actor,
    )
    return hmac.new(
        str(secret).encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _register_nonce_or_reject(*, nonce: str, now_ts: int, window_seconds: int) -> None:
    try:
        accepted = register_nonce_once(
            nonce=nonce,
            now_ts=int(now_ts),
            window_seconds=int(window_seconds),
        )
    except SecurityStateUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Security state backend is unavailable.",
        ) from exc
    if not accepted:
        raise HTTPException(status_code=401, detail="Replay request rejected.")


async def _verify_request_signature(
    *,
    request: Request,
    supplied_signature: str | None,
    supplied_timestamp: str | None,
    supplied_nonce: str | None,
    supplied_key_id: str | None = None,
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
    key_id = str(supplied_key_id or "").strip()
    if not signature or not timestamp_raw or not nonce:
        raise HTTPException(status_code=401, detail="Missing signed request headers.")

    # Key rotation: when the deployment advertises a key ID, callers must send
    # a matching x-okr-key-id. Unknown IDs are rejected; omitted ID is accepted
    # only while no key ID is advertised (pre-rotation deployments).
    advertised_key_id = str(settings.signing_key_id or "").strip()
    if advertised_key_id:
        if not key_id:
            raise HTTPException(
                status_code=401,
                detail="Missing signing key ID header.",
            )
        if key_id != advertised_key_id and key_id != "previous":
            raise HTTPException(
                status_code=401,
                detail="Unknown signing key ID.",
            )

    try:
        timestamp_int = int(timestamp_raw)
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail="Invalid request timestamp."
        ) from exc

    now_ts = int(time.time())
    if abs(now_ts - timestamp_int) > int(settings.request_signing_window_seconds):
        raise HTTPException(status_code=401, detail="Request signature expired.")

    body = await request.body()
    session_id = request.headers.get("x-okr-session-id")
    session_actor = request.headers.get("x-okr-session-actor")

    def _try_signature(candidate_secret: str) -> bool:
        expected = _expected_signature(
            method=request.method,
            path=str(request.url.path or "/"),
            timestamp=timestamp_raw,
            nonce=nonce,
            body=body,
            secret=candidate_secret,
            session_id=session_id,
            session_actor=session_actor,
        )
        return secrets.compare_digest(signature, expected)

    # Overlap window: accept signatures made with either the current secret or
    # the previous one (rotation transition). The literal ID "previous" forces
    # verification against the previous secret only.
    previous_secret = str(settings.signing_secret_previous or "").strip()
    signature_valid = False
    if key_id == "previous":
        if not previous_secret:
            raise HTTPException(
                status_code=401,
                detail="No previous signing key configured.",
            )
        signature_valid = _try_signature(previous_secret)
    else:
        signature_valid = _try_signature(secret)
        if not signature_valid and previous_secret:
            signature_valid = _try_signature(previous_secret)

    if not signature_valid:
        raise HTTPException(status_code=401, detail="Invalid request signature.")

    # Replay protection writes to shared security state; keep it off the event loop,
    # because this dependency is awaited on the loop and every request passes here.
    await run_in_threadpool(
        _register_nonce_or_reject,
        nonce=nonce,
        now_ts=now_ts,
        window_seconds=settings.request_signing_window_seconds,
    )


async def require_service_access(
    request: Request,
    x_okr_actor: str | None = Header(default=None),
    x_okr_role: str | None = Header(default=None),
    x_okr_roles: str | None = Header(default=None),
    x_okr_token_version: str | None = Header(default=None, include_in_schema=False),
    x_okr_service_token: str | None = Header(default=None),
    x_okr_signature: str | None = Header(default=None),
    x_okr_timestamp: str | None = Header(default=None),
    x_okr_nonce: str | None = Header(default=None),
    x_okr_key_id: str | None = Header(default=None),
) -> None:
    settings = get_backend_settings()
    # This dependency is the first thing every protected request runs, so it is the
    # right place to start a clean per-request scope cache. Without this reset a
    # recycled execution context could hand one actor's resolved scope to the next
    # request, which would be an authorization leak rather than a performance bug.
    # Imported lazily because scope_resolution imports from this module.
    from backend_app.scope_resolution import reset_request_scope_cache

    reset_request_scope_cache()
    service_token_valid = False

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
        service_token_valid = True

    if settings.enforce_request_signing:
        await _verify_request_signature(
            request=request,
            supplied_signature=x_okr_signature,
            supplied_timestamp=x_okr_timestamp,
            supplied_nonce=x_okr_nonce,
            supplied_key_id=x_okr_key_id,
        )
        service_token_valid = True

    # Rate limit by client IP, taken only from a source the caller cannot choose.
    #
    # `X-Forwarded-For` is deliberately NOT read here. `deploy/nginx.conf` sets it with
    # `$proxy_add_x_forwarded_for`, which APPENDS to whatever the client sent, so its
    # leftmost entry is caller-supplied. Keying on that entry let a caller rotate the
    # rate-limit key per request and so bypass the limit while appearing to respect it.
    # The private header below is overwritten at every hop and is honoured only on a
    # request already authenticated as originating from the BFF. See
    # docs/client-ip-trust-adr.md.
    #
    # The peer address stays as the fallback on purpose: with no trusted address this
    # degrades to an aggregate limit over the proxy, which is undesirable but is still
    # a limit, whereas dropping the key entirely would drop the control. The login
    # lockout draws the opposite conclusion for the opposite reason - a shared bucket
    # there would lock out every user, so it stays unkeyed (see api_auth_login).
    # Publish the trusted address for dependents that cannot re-derive it, such as the
    # login lockout (see api_auth_login). Fail-closed: a request whose service token and
    # signature were both unverified publishes None, so the lockout's IP dimension stays
    # inert rather than keying on a value a caller can choose.
    request.state.trusted_client_ip = None

    client_ip = request.client.host if request.client else "unknown"
    if service_token_valid:
        trusted_client_ip = (request.headers.get("x-okr-client-ip") or "").strip()
        if trusted_client_ip:
            client_ip = trusted_client_ip
            request.state.trusted_client_ip = trusted_client_ip

    try:
        # This dependency is `async` because it awaits `request.body()`, and it is
        # awaited on the event loop, so synchronous database work here blocks every
        # concurrent request. The suite forces OKR_BACKEND_API_WORKERS=1, which makes
        # that serialisation total. The calls below are therefore dispatched to the
        # threadpool rather than turned into a `def` dependency, which is not possible
        # while the body read must be awaited.
        rl_ok = await run_in_threadpool(
            check_rate_limit,
            key=f"ip:{client_ip}",
            limit=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
    except SecurityStateUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Security state backend is unavailable.",
        ) from exc
    if not rl_ok:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    route = request.scope.get("route")
    route_path = str(getattr(route, "path", "") or request.url.path or "")
    is_login = route_path in {"/v1/auth/login", "/api/v1/auth/login"}
    is_versioned_api = route_path.startswith(("/v1/", "/api/v1/"))
    actor_header = str(x_okr_actor or "").strip()
    actor_bound = bool(actor_header) or (
        is_versioned_api
        and not is_login
        and not bool(getattr(request.state, "actorless_service_access", False))
    )
    if actor_bound and not actor_header:
        raise HTTPException(
            status_code=401, detail="Actor-bound route requires a signed actor."
        )

    current_scope = None
    if actor_header:
        supplied_version = str(x_okr_token_version or "").strip()
        if (
            not supplied_version.isascii()
            or not supplied_version.isdecimal()
            or supplied_version.startswith("0")
        ):
            raise HTTPException(
                status_code=401, detail="Valid session token version required."
            )
        token_version = int(supplied_version)
        if token_version <= 0:
            raise HTTPException(
                status_code=401, detail="Valid session token version required."
            )
        try:
            current_scope = await run_in_threadpool(
                _resolve_current_actor_scope,
                actor_header,
                token_version,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Current account state is unavailable."
            ) from exc

        raw_session_id = str(request.headers.get("x-okr-session-id") or "")
        session_id = raw_session_id
        raw_session_actor = str(request.headers.get("x-okr-session-actor") or "")
        session_actor = raw_session_actor
        if (
            len(session_id) < 16
            or len(session_id) > 512
            or not session_id.isascii()
            or any(ord(char) < 0x21 or ord(char) > 0x7E for char in session_id)
            or raw_session_actor != raw_session_actor.strip()
            or not session_actor
        ):
            raise HTTPException(
                status_code=401, detail="Valid signed session assertions required."
            )
        actor_id = current_scope.get("actor_id") if current_scope else None
        if actor_id is None:
            raise HTTPException(
                status_code=503, detail="Current account state is unavailable."
            )
        try:
            resolved_actor_id = int(actor_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Current account state is unavailable."
            ) from exc
        if resolved_actor_id <= 0 or session_actor != str(resolved_actor_id):
            raise HTTPException(status_code=401, detail="Session actor mismatch.")
        try:
            session_status = await run_in_threadpool(
                check_session,
                session_digest=hashlib.sha256(session_id.encode("utf-8")).hexdigest(),
                actor_id=str(resolved_actor_id),
                now=datetime.now(timezone.utc),
            )
        except SecurityStateUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="Session verification is unavailable."
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Session verification is unavailable."
            ) from exc
        if session_status != "active":
            raise HTTPException(status_code=401, detail="Session is not active.")

    await run_in_threadpool(
        validate_forwarded_role_claims,
        actor=x_okr_actor,
        x_okr_role=x_okr_role,
        x_okr_roles=x_okr_roles,
        scope=current_scope,
    )


def _resolve_current_actor_scope(actor: str, token_version: int) -> dict:
    from backend_app import main as backend_main

    return backend_main._resolve_scope_for_actor(actor, token_version=token_version)


def _normalize_forwarded_role_claim(value: str | None) -> set[str]:
    values: set[str] = set()
    for item in str(value or "").split(","):
        text = str(item or "").strip().lower()
        if not text:
            continue
        values.add(text)
        if text.startswith("atlas-"):
            values.add(text.removeprefix("atlas-"))
    normalized: set[str] = set()
    for item in values:
        if item in {"admin", "manager", "member"}:
            normalized.add(item)
        elif item.startswith("atlas-"):
            normalized.add(item.removeprefix("atlas-"))
    return normalized


def validate_forwarded_role_claims(
    *,
    actor: str | None,
    x_okr_role: str | None,
    x_okr_roles: str | None,
    scope: dict | None = None,
) -> None:
    if not actor:
        return
    actor_name = str(actor).strip()
    if not actor_name:
        return
    if not x_okr_role and not x_okr_roles:
        return

    if scope is None:
        try:
            from backend_app import main as backend_main

            scope = backend_main._resolve_scope_for_actor(actor_name)
        except Exception:
            return

    expected_role = str(scope.get("role") or "").strip().lower()
    if not expected_role:
        return

    if x_okr_role:
        normalized_role_claim = _normalize_forwarded_role_claim(x_okr_role)
        if not normalized_role_claim or expected_role not in normalized_role_claim:
            raise HTTPException(
                status_code=403,
                detail="Role claim does not match actor scope.",
            )

    if x_okr_roles:
        normalized_roles_claim = _normalize_forwarded_role_claim(x_okr_roles)
        if not normalized_roles_claim or expected_role not in normalized_roles_claim:
            raise HTTPException(
                status_code=403,
                detail="Role claim does not match actor scope.",
            )


def resolve_actor_username(
    *,
    header_actor: str | None,
    payload_actor: str | None,
) -> str:
    header = str(header_actor or "").strip()
    payload = str(payload_actor or "").strip()

    if header and payload and header != payload:
        raise HTTPException(
            status_code=403,
            detail="Actor mismatch: header and payload actors differ. Use the session actor.",
        )

    actor = header or payload
    if not actor:
        raise HTTPException(status_code=400, detail="Actor username is required.")
    if len(actor) > 128:
        raise HTTPException(status_code=400, detail="Actor username is too long.")
    return actor


def _reset_security_state_for_tests() -> None:
    """Test-only helper to clear replay/rate state between test cases."""
    reset_security_state_for_tests()
