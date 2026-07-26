"""Router module for AI analysis endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from backend_app.schemas import (
    AiAnalyzeNodeRequest,
    AiStrategyPulseRequest,
    AiTeamCoachRequest,
)


def register_ai_routes(router: APIRouter, main: Any) -> None:
    """Register AI helper endpoints."""

    @router.post(
        "/v1/ai/analyze-node",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_ai_analyze_node(
        payload: AiAnalyzeNodeRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
        node_type = str(payload.node_type or "KEY_RESULT")
        actor_role = None
        actor_team_id = None
        try:
            actor_user = main.get_user_by_username(actor)
        except Exception:
            main._LOGGER.warning(
                "Failed to look up actor user '%s' for AI analysis; proceeding without role context",
                actor,
                exc_info=True,
            )
            actor_user = None
        if actor_user:
            raw_role = getattr(actor_user, "role", None)
            actor_role = getattr(raw_role, "value", None) or (
                str(raw_role) if raw_role else None
            )
            actor_team_id = getattr(actor_user, "team_id", None)
        base_details = {
            "node_id": int(payload.node_id),
            "node_type": node_type,
            "feature": "ai_analyze_node",
        }
        if actor_role:
            base_details["actor_role"] = actor_role
        if actor_team_id is not None:
            base_details["actor_team_id"] = actor_team_id
        result = main.analyze_node(
            int(payload.node_id),
            node_type,
            actor_username=actor,
        )
        if not isinstance(result, dict):
            main.audit_log(
                action="analyze",
                entity="ai_node",
                actor=actor,
                target_type="node",
                target_id=int(payload.node_id),
                details={
                    **base_details,
                    "success": False,
                    "result": "failure",
                    "error_type": "invalid_payload",
                    "error_text": "AI analysis returned invalid payload.",
                },
            )
            raise HTTPException(
                status_code=500, detail="AI analysis returned invalid payload."
            )
        error_text = str(result.get("error") or "").strip()
        if error_text:
            lowered = error_text.lower()
            error_type = "validation_error"
            if "not found" in lowered:
                error_type = "not_found"
                main.audit_log(
                    action="analyze",
                    entity="ai_node",
                    actor=actor,
                    target_type="node",
                    target_id=int(payload.node_id),
                    details={
                        **base_details,
                        "success": False,
                        "result": "failure",
                        "error_type": error_type,
                        "error_text": error_text,
                    },
                )
                raise HTTPException(status_code=404, detail=error_text)
            if (
                "permission" in lowered
                or "forbidden" in lowered
                or "authorized" in lowered
            ):
                error_type = "forbidden"
                main.audit_log(
                    action="analyze",
                    entity="ai_node",
                    actor=actor,
                    target_type="node",
                    target_id=int(payload.node_id),
                    details={
                        **base_details,
                        "success": False,
                        "result": "failure",
                        "error_type": error_type,
                        "error_text": error_text,
                    },
                )
                raise HTTPException(status_code=403, detail=error_text)
            main.audit_log(
                action="analyze",
                entity="ai_node",
                actor=actor,
                target_type="node",
                target_id=int(payload.node_id),
                details={
                    **base_details,
                    "success": False,
                    "result": "failure",
                    "error_type": error_type,
                    "error_text": error_text,
                },
            )
            raise HTTPException(status_code=400, detail=error_text)
        main.audit_log(
            action="analyze",
            entity="ai_node",
            actor=actor,
            target_type="node",
            target_id=int(payload.node_id),
            details={
                **base_details,
                "success": True,
                "result": "success",
                "overall_score": result.get("overall_score"),
            },
        )
        return result

    @router.post(
        "/v1/ai/team-coach",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_ai_team_coach(
        payload: AiTeamCoachRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_token_version: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
        token_version = int(x_okr_token_version) if x_okr_token_version else None
        with main.get_session_context() as session:
            main._resolve_actor_scope(session, actor, token_version=token_version)
        result = main.analyze_team_health(dict(payload.team_data or {}))
        if not isinstance(result, dict):
            raise HTTPException(
                status_code=500, detail="AI team coach returned invalid payload."
            )
        error_text = str(result.get("error") or "").strip()
        if error_text:
            raise HTTPException(status_code=400, detail=error_text)
        return result

    @router.post(
        "/v1/ai/strategy-pulse",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_ai_strategy_pulse(
        payload: AiStrategyPulseRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_token_version: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
        token_version = int(x_okr_token_version) if x_okr_token_version else None
        with main.get_session_context() as session:
            scope = main._resolve_actor_scope(
                session, actor, token_version=token_version
            )
        allowed_usernames = {
            str(value).strip() for value in (scope.get("usernames") or set())
        }
        subject_username = str(payload.subject_username or actor).strip()
        if not subject_username:
            raise HTTPException(status_code=400, detail="Subject username is required.")
        if subject_username not in allowed_usernames:
            raise HTTPException(status_code=403, detail="Actor is not authorized.")

        subject_user = main.get_user_by_username(subject_username)
        if not subject_user:
            raise HTTPException(status_code=404, detail="User not found.")

        cycle_id = int(payload.cycle_id)
        subject_user_id = int(getattr(subject_user, "id", 0) or 0)
        if subject_user_id <= 0:
            raise HTTPException(status_code=404, detail="User not found.")

        burnout = main.calculate_burnout_risk(subject_user_id, days=int(payload.days))
        gaps = main.detect_strategy_gaps(cycle_id, user_ids=[subject_user_id])
        cycle_title = (
            str(payload.cycle_title or f"Cycle {cycle_id}").strip()
            or f"Cycle {cycle_id}"
        )
        outlook = main.generate_predictive_outlook(
            burnout_data=burnout,
            strategy_gaps=gaps,
            cycle_title=cycle_title,
        )
        if not isinstance(outlook, dict):
            raise HTTPException(
                status_code=500, detail="AI strategy pulse returned invalid payload."
            )
        error_text = str(outlook.get("error") or "").strip()
        if error_text:
            raise HTTPException(status_code=400, detail=error_text)

        gap_signals = [
            (
                f"{str(gap.get('title') or 'Untitled').strip()}: "
                f"{str(gap.get('gap_type') or 'N/A').strip()} "
                f"(severity {int(gap.get('severity') or 0)})"
            )
            for gap in (gaps or [])[:5]
        ]
        portfolio_actions = main._coerce_string_list(
            outlook.get("risk_mitigation")
        ) + main._coerce_string_list(outlook.get("strategic_pivots"))

        return {
            "subject_username": subject_username,
            "cycle_id": cycle_id,
            "burnout_snapshot": burnout,
            "strategy_gaps": gaps,
            "predictive_outlook": outlook,
            "burnout_risk": str(burnout.get("risk_label") or "").strip(),
            "gap_signals": gap_signals,
            "portfolio_actions": portfolio_actions,
        }
