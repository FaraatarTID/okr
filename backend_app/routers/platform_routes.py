from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from backend_app.schemas import (
    AtlasSnapshotRequest,
    AuthLoginResponse,
    AuthSessionResponse,
    LeadershipMetricsRequest,
    LoginRequest,
    ReadQueryRequest,
    ReadQueryResponse,
)
from src.services.app_shell_runtime import serialize_user


def register_platform_routes(router: APIRouter, main: Any) -> None:
    """Register platform-facing /auth, read-only, admin, and system routes."""

    def _effective_read_mode() -> str:
        from backend_app.data_access_mode import resolve_read_mode

        return resolve_read_mode()

    @router.post(
        "/v1/auth/login",
        dependencies=[Depends(main.require_service_access)],
        response_model=AuthLoginResponse,
        response_model_exclude_unset=True,
    )
    def api_auth_login(payload: LoginRequest) -> dict:
        from backend_app.data_access_mode import notify_tcp_db_failure, resolve_read_mode

        use_https = main.is_supabase_api_mode_enabled()
        try:
            if not use_https and resolve_read_mode() == "supabase_api":
                # TCP unreachable but HTTPS available: probe scope resolution
                # will have already failed over; auth follows the same path.
                use_https = True
            if use_https:
                auth = main.authenticate_user_detailed_via_supabase_api(
                    username=str(payload.username or "").strip(),
                    password=payload.password,
                    client_ip=(
                        str(payload.client_ip).strip() if payload.client_ip else None
                    ),
                )
            else:
                auth = main.authenticate_user_detailed(
                    username=str(payload.username or "").strip(),
                    password=payload.password,
                    client_ip=(
                        str(payload.client_ip).strip() if payload.client_ip else None
                    ),
                )
        except Exception:
            if not use_https:
                notify_tcp_db_failure()
                if resolve_read_mode() == "supabase_api":
                    auth = main.authenticate_user_detailed_via_supabase_api(
                        username=str(payload.username or "").strip(),
                        password=payload.password,
                        client_ip=(
                            str(payload.client_ip).strip()
                            if payload.client_ip
                            else None
                        ),
                    )
                else:
                    raise
            else:
                raise
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
        if main.is_supabase_api_mode_enabled():
            scope = main._resolve_scope_for_actor(actor, token_version=token_version)
            user_data = scope
        else:
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
        "/v1/read/query",
        dependencies=[Depends(main.require_service_access)],
        response_model=ReadQueryResponse,
        response_model_exclude_none=True,
    )
    def api_read_query(
        payload: ReadQueryRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
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

    @router.get("/healthz")
    def healthz() -> dict:
        from backend_app.data_access_mode import effective_mode_report

        try:
            dead_jobs = main.count_dead_jobs()
        except Exception:
            dead_jobs = None
        return {
            "status": "ok",
            "data_access_mode": effective_mode_report(),
            "configured_mode": (
                "supabase_api" if main.is_supabase_api_mode_enabled() else "database"
            ),
            "dead_jobs": dead_jobs,
        }

    @router.get(
        "/v1/admin/ai-health",
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
        dependencies=[Depends(main.require_service_access)],
    )
    def api_admin_db_backup(
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> Response:
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        backup_bytes = main.export_database_backup()
        return Response(content=backup_bytes, media_type="application/json")

    @router.post(
        "/v1/admin/db-restore",
        dependencies=[Depends(main.require_service_access)],
    )
    async def api_admin_db_restore(
        request: Request,
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

        # Enforce body size limit (50 MB)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size_bytes = int(content_length)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400, detail="Invalid Content-Length header."
                )
            if size_bytes > 50 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="Request body too large. Maximum 50 MB.",
                )

        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400, detail="Backup restore payload must be a JSON object."
            )
        if str(payload.get("format") or "").strip() != main.BACKUP_FORMAT_VERSION:
            raise HTTPException(
                status_code=400, detail="Unsupported backup format version."
            )

        # Audit the restore attempt
        main.audit_log(
            "restore_attempt",
            "database",
            actor=actor,
            details={
                "format": payload.get("format"),
                "tables": list(payload.keys())[:10],
            },
        )

        try:
            return dict(main.import_database_backup(payload))
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
        if _effective_read_mode() == "supabase_api":
            return main.build_atlas_scope_snapshot_via_supabase_api(
                cycle_id=int(cycle_id),
                owner_ids=owner_ids,
                include_analysis=bool(payload.include_analysis),
                actor=actor,
            )
        with main.get_session_context() as session:
            return main.build_atlas_scope_snapshot(
                session,
                cycle_id=int(cycle_id),
                owner_ids=owner_ids,
                include_analysis=bool(payload.include_analysis),
            )

    @router.post(
        "/v1/read/leadership/metrics",
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
        if _effective_read_mode() == "supabase_api":
            return main.get_leadership_metrics_via_supabase_api(
                usernames=list(usernames),
                cycle_id=int(cycle_id),
                actor=actor,
            )
        return main.get_leadership_metrics(usernames, int(cycle_id))
