from __future__ import annotations

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from backend_app.security_state import is_session_registry_state_key
from backend_app.schemas import (
    AdminAiHealthResponse,
    AdminDbRestoreRequest,
    AdminDbRestoreResponse,
    AdminPdfHealthResponse,
    AuthPasswordChangeRequest,
    AuthPasswordChangeResponse,
    AtlasSnapshotRequest,
    AtlasSnapshotResponse,
    AuthLoginResponse,
    AuthSessionResponse,
    LeadershipMetricsRequest,
    LeadershipMetricsResponse,
    LoginRequest,
    ReadQueryRequest,
    ReadQueryResponse,
)
from src.services.app_shell_runtime import serialize_user
from src.observability import record_timing
from src.saas.identity_contract import enforce_enterprise_login_policy


def register_platform_routes(router: APIRouter, main: Any) -> None:
    """Register platform-facing /auth, read-only, admin, and system routes."""

    async def _timed_service_access(
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
        dependency_started_at = time.perf_counter()
        try:
            await main.require_service_access(
                request=request,
                x_okr_actor=x_okr_actor,
                x_okr_role=x_okr_role,
                x_okr_roles=x_okr_roles,
                x_okr_token_version=x_okr_token_version,
                x_okr_service_token=x_okr_service_token,
                x_okr_signature=x_okr_signature,
                x_okr_timestamp=x_okr_timestamp,
                x_okr_nonce=x_okr_nonce,
                x_okr_key_id=x_okr_key_id,
            )
        finally:
            record_timing(
                "dependency", (time.perf_counter() - dependency_started_at) * 1000
            )

    @router.post(
        "/v1/auth/login",
        dependencies=[Depends(main.require_service_access)],
        response_model=AuthLoginResponse,
        response_model_exclude_unset=True,
    )
    def api_auth_login(request: Request, payload: LoginRequest) -> dict:
        username = str(payload.username or "").strip()
        # The IP dimension of the login throttle keys on the trusted client address
        # published by `require_service_access`, which this route already depends on, so
        # the check is not repeated here.
        #
        # The address is never taken from `payload`: a body-supplied address is chosen by
        # the caller, and the lockout table is keyed (scope="ip", identifier), so
        # honouring it would hand the caller the ability to lock out any address it
        # names. The peer address is not used either - it is the shared BFF, so every
        # user would land in one bucket and a single attacker could lock out all of
        # them. When no verified address is available the dimension stays inert, which
        # is the intended failure direction: a missing lockout dimension is visible,
        # whereas a wrong key is not. See docs/client-ip-trust-adr.md.
        client_ip = getattr(request.state, "trusted_client_ip", None)
        try:
            enforce_enterprise_login_policy(username)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        auth = main.authenticate_user_detailed(
            username=str(payload.username or "").strip(),
            password=payload.password,
            client_ip=client_ip,
        )
        output = dict(auth or {})
        output["user"] = serialize_user((auth or {}).get("user"))
        return output

    @router.get(
        "/v1/auth/me",
        dependencies=[Depends(main.require_service_access)],
        response_model=AuthSessionResponse,
    )
    def api_get_current_user(
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_token_version: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        if not actor:
            raise HTTPException(status_code=401, detail="No active session.")
        token_version = int(x_okr_token_version) if x_okr_token_version else None
        with main.get_session_context() as session:
            main._resolve_actor_scope(session, actor, token_version=token_version)
            user = session.exec(
                main.select(main.User).where(main.User.username == actor)
            ).first()
            if not user:
                raise HTTPException(status_code=401, detail="User not found.")
            user_data = {
                "actor_id": user.id,
                "username": user.username,
                "display_name": getattr(user, "display_name", "") or "",
                "role": getattr(user, "role", "member"),
                "team_id": getattr(user, "team_id", None),
                "manager_id": getattr(user, "manager_id", None),
                "must_change_password": bool(
                    getattr(user, "must_change_password", False)
                ),
                "token_version": getattr(user, "token_version", 1),
            }
        return {
            "id": user_data.get("actor_id"),
            "username": actor,
            "display_name": user_data.get("display_name", ""),
            "role": user_data.get("role", "member"),
            "team_id": user_data.get("team_id"),
            "manager_id": user_data.get("manager_id"),
            "must_change_password": user_data.get("must_change_password", False),
            "token_version": user_data.get("token_version"),
        }

    @router.post(
        "/v1/auth/change-password",
        dependencies=[Depends(main.require_service_access)],
        response_model=AuthPasswordChangeResponse,
    )
    def api_change_own_password(
        request: Request,
        payload: AuthPasswordChangeRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_token_version: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        token_version: Optional[int] = None
        if x_okr_token_version:
            try:
                token_version = int(x_okr_token_version)
            except ValueError as exc:
                raise HTTPException(
                    status_code=401, detail="Session is no longer valid."
                ) from exc

        try:
            with main.get_session_context() as session:
                main._resolve_actor_scope(session, actor, token_version=token_version)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Password change is temporarily unavailable."
            ) from exc

        client_ip = getattr(request.state, "trusted_client_ip", None)

        try:
            auth = main.authenticate_user_detailed(
                username=actor,
                password=payload.current_password,
                client_ip=client_ip,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Password change is temporarily unavailable.",
            ) from exc

        auth = dict(auth or {})
        error_code = str(auth.get("error_code") or "")
        if not auth.get("success"):
            if error_code.startswith("AUTH_LOCKED"):
                retry_after = max(int(auth.get("retry_after_seconds") or 1), 1)
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            if error_code == "AUTH_BACKEND_UNAVAILABLE":
                raise HTTPException(
                    status_code=503,
                    detail="Password change is temporarily unavailable.",
                )
            raise HTTPException(
                status_code=401, detail="Current password is incorrect."
            )

        user = auth.get("user")
        user_id = getattr(user, "id", None)
        if user_id is None or str(getattr(user, "username", "")) != actor:
            raise HTTPException(status_code=401, detail="Session is no longer valid.")

        try:
            updated = main.reset_user_password(
                user_id=int(user_id),
                new_password=payload.new_password,
                require_change=False,
                actor_username=actor,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=main._status_for_value_error(str(exc)), detail=str(exc)
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Password change is temporarily unavailable."
            ) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="User not found.")
        return {"updated": True}

    @router.post(
        "/v1/read/query",
        dependencies=[Depends(_timed_service_access)],
        response_model=ReadQueryResponse,
        response_model_exclude_none=True,
    )
    def api_read_query(
        payload: ReadQueryRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        try:
            handler_started_at = time.perf_counter()
            actor_started_at = time.perf_counter()
            try:
                actor = main._resolve_actor(
                    header_actor=x_okr_actor,
                    payload_actor=payload.actor_username,
                )
            finally:
                record_timing("actor", (time.perf_counter() - actor_started_at) * 1000)
            try:
                return main._read_query_payload(
                    kind=str(payload.kind or "").strip(),
                    params=dict(payload.params or {}),
                    actor=actor,
                )
            except HTTPException:
                raise
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=main._status_for_value_error(str(exc)),
                    detail=str(exc),
                ) from exc
            except Exception as exc:
                main.error_log("backend_read_query_unhandled_error", exc)
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected server error while processing read query.",
                ) from exc
        finally:
            record_timing("handler", (time.perf_counter() - handler_started_at) * 1000)

    @router.get("/healthz")
    def healthz() -> dict:
        try:
            dead_jobs = main.count_dead_jobs()
        except Exception:
            dead_jobs = None
        return {
            "status": "ok",
            "data_access_mode": "database",
            "configured_mode": "database",
            "dead_jobs": dead_jobs,
        }

    @router.get(
        "/v1/admin/ai-health",
        response_model=AdminAiHealthResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_admin_ai_health(
        live_probe: bool = False,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        return main.run_ai_health_check(live_probe=bool(live_probe))

    @router.get(
        "/v1/admin/pdf-health",
        response_model=AdminPdfHealthResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_admin_pdf_health(
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        return dict(main.get_pdf_runtime_diagnostics())

    @router.get(
        "/v1/admin/observability/metrics",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_admin_observability_metrics(
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        return main.get_observability_metrics_snapshot()

    @router.get(
        "/v1/admin/db-backup",
        response_class=Response,
        responses={
            200: {
                "description": "Database backup export.",
                "content": {
                    "application/octet-stream": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
                "headers": {
                    "Content-Disposition": {
                        "description": "Suggested attachment filename.",
                        "schema": {"type": "string"},
                    }
                },
            }
        },
        dependencies=[Depends(main.require_service_access)],
    )
    def api_admin_db_backup(
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> Response:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        backup_bytes = main.export_database_backup()
        return Response(
            content=backup_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": 'attachment; filename="okr-db-backup.json"'
            },
        )

    @router.post(
        "/v1/admin/db-restore",
        response_model=AdminDbRestoreResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    async def api_admin_db_restore(
        request: Request,
        payload: AdminDbRestoreRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        if not main.get_bool_config("OKR_ENABLE_DIRECT_DB_RESTORE", False):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Direct DB restore is disabled. "
                    "Set OKR_ENABLE_DIRECT_DB_RESTORE=true for controlled admin restore."
                ),
            )
        if main.is_production_runtime():
            raise HTTPException(
                status_code=403,
                detail="Direct DB restore is blocked in production runtime.",
            )

        # The 50 MB body ceiling is enforced before the body is read, by
        # RouteBodyLimitMiddleware (backend_app/body_limit.py). A check here would run only
        # after the whole body was already parsed into memory, so it bounded nothing.

        payload_data = payload.model_dump()
        if str(payload_data.get("format") or "").strip() != main.BACKUP_FORMAT_VERSION:
            raise HTTPException(
                status_code=400, detail="Unsupported backup format version."
            )

        # Audit the restore attempt
        main.audit_log(
            "restore_attempt",
            "database",
            actor=actor,
            details={
                "format": payload_data.get("format"),
                "tables": list(payload_data.keys())[:10],
            },
        )

        try:
            return dict(main.import_database_backup(payload_data))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/v1/state/{key}",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_get_app_state(
        key: str,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        main._require_admin_actor_scope(str(x_okr_actor or ""))
        if is_session_registry_state_key(key):
            raise HTTPException(
                status_code=400,
                detail="The session-registry state namespace is reserved.",
            )
        value = main.get_app_state(key)
        return {"key": key, "value": value}

    @router.post(
        "/v1/state/{key}",
        dependencies=[Depends(main.require_service_access)],
    )
    async def api_set_app_state(
        key: str,
        request: Request,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        main._require_admin_actor_scope(str(x_okr_actor or ""))
        if is_session_registry_state_key(key):
            raise HTTPException(
                status_code=400,
                detail="The session-registry state namespace is reserved.",
            )
        # Accept raw text/plain or json-wrapped value
        try:
            body = await request.body()
            raw_value = body.decode("utf-8")
            # Try if it's JSON {"value": "..."}
            try:
                data = json.loads(raw_value)
                if isinstance(data, dict) and "value" in data:
                    value = str(data["value"])
                else:
                    value = raw_value
            except json.JSONDecodeError:
                value = raw_value

            main.set_app_state(key, value)
            return {"key": key, "value": value, "status": "updated"}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post(
        "/v1/read/atlas/snapshot",
        response_model=AtlasSnapshotResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_read_atlas_snapshot(
        payload: AtlasSnapshotRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
        requested_owner_ids = main._coerce_owner_ids(payload.owner_ids)
        scope = main._resolve_scope_for_actor(actor)
        allowed_owner_ids = set(scope.get("owner_ids") or set())
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope, int(payload.cycle_id)
        )
        if bool(scope.get("is_admin", False)):
            owner_ids = requested_owner_ids or None
        else:
            if requested_owner_ids:
                owner_ids = sorted(
                    allowed_owner_ids.intersection(set(requested_owner_ids))
                )
            else:
                owner_ids = sorted(allowed_owner_ids)
        with main.get_session_context() as session:
            return main.build_atlas_scope_snapshot(
                session,
                cycle_id=int(cycle_id),
                owner_ids=owner_ids,
                include_analysis=bool(payload.include_analysis),
            )

    @router.post(
        "/v1/read/leadership/metrics",
        response_model=LeadershipMetricsResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_read_leadership_metrics(
        payload: LeadershipMetricsRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
        requested_usernames = {
            str(value).strip()
            for value in (payload.usernames or [])
            if str(value).strip()
        }
        scope = main._resolve_scope_for_actor(actor)
        allowed_usernames = {str(value) for value in (scope.get("usernames") or set())}
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope, int(payload.cycle_id)
        )
        if bool(scope.get("is_admin", False)):
            usernames = (
                sorted(requested_usernames)
                if requested_usernames
                else sorted(allowed_usernames)
            )
        else:
            usernames = (
                sorted(allowed_usernames.intersection(requested_usernames))
                if requested_usernames
                else sorted(allowed_usernames)
            )
        if not usernames:
            return {}
        return main.get_leadership_metrics(usernames, int(cycle_id))
