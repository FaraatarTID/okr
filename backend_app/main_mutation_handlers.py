from __future__ import annotations

from typing import Optional, Type, cast

from fastapi import Header, HTTPException
from pydantic import BaseModel, ValidationError as PydanticValidationError

from backend_app.input_normalization import (
    _normalize_node_type,
    _normalize_tags,
    _normalize_updates,
    _coerce_enum,
    _cycle_view_from_obj,
    _node_view_from_obj,
    _team_view_from_obj,
    _user_view_from_obj,
)
from backend_app.main_runtime_helpers import (
    _atomic_idempotent_check,
    _complete_idempotent_response,
    _payload_to_jsonable,
    _require_admin_actor_scope,
    _require_admin_or_manager_actor_scope,
    _resolve_actor,
    _resolve_scope_for_actor,
    _status_for_value_error,
)
from backend_app.response_scope_helpers import (
    _require_allowed_user_id,
    _resolve_goal_owner_id_for_node_via_supabase,
)
from src.crud import (
    create_cycle,
    create_team,
    delete_cycle,
    delete_team,
    reset_user_password,
    update_cycle,
    update_team,
    update_user,
)
from src.models import UserRole
from src.services.supabase_api_mode import (
    create_cycle_via_supabase_api,
    create_team_via_supabase_api,
    delete_cycle_via_supabase_api,
    delete_node_via_supabase_api,
    delete_team_via_supabase_api,
    is_supabase_api_mode_enabled,
    reset_user_password_via_supabase_api,
    update_cycle_via_supabase_api,
    update_node_via_supabase_api,
    update_team_via_supabase_api,
    update_user_via_supabase_api,
)


from backend_app.schemas import (
    CycleCreateRequest,
    CycleDeleteResponse,
    CycleMutationView,
    CycleUpdateRequest,
    GoalCreateRequest,
    GoalUpdateRequest,
    KeyResultCreateRequest,
    KeyResultUpdateRequest,
    NodeDeleteResponse,
    NodeMutationView,
    NodeUpdateRequest,
    ObjectiveCreateRequest,
    ObjectiveUpdateRequest,
    TeamCreateRequest,
    TeamDeleteResponse,
    TeamMutationView,
    TeamUpdateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
    UserCreateRequest,
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserUpdateRequest,
    UserMutationView,
)


def _resolve_backend_main():
    import backend_app.main as backend_main

    return backend_main
 


def api_create_goal(
    payload: GoalCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username or payload.user_id,
    )
    idempotency_scope = "goals.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("GOAL", replay)
    try:
        if _resolve_backend_main().is_supabase_api_mode_enabled():
            goal = _resolve_backend_main().create_goal_via_supabase_api(
                user_id=payload.user_id,
                title=payload.title,
                description=payload.description,
                cycle_id=payload.cycle_id,
                strategy_tags=_normalize_tags(payload.strategy_tags),
                actor_username=actor,
            )
        else:
            goal = _resolve_backend_main().create_goal(
                user_id=payload.user_id,
                title=payload.title,
                description=payload.description,
                cycle_id=payload.cycle_id,
                strategy_tags=_normalize_tags(payload.strategy_tags),
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = _node_view_from_obj("GOAL", goal)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


def api_create_objective(
    payload: ObjectiveCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "objectives.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("OBJECTIVE", replay)
    try:
        if _resolve_backend_main().is_supabase_api_mode_enabled():
            objective = _resolve_backend_main().create_objective_via_supabase_api(
                goal_id=payload.goal_id,
                title=payload.title,
                description=payload.description,
                weight=payload.weight,
                actor_username=actor,
            )
        else:
            objective = _resolve_backend_main().create_objective(
                goal_id=payload.goal_id,
                title=payload.title,
                description=payload.description,
                weight=payload.weight,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = _node_view_from_obj("OBJECTIVE", objective)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


def api_create_key_result(
    payload: KeyResultCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "key_results.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("KEY_RESULT", replay)
    try:
        if _resolve_backend_main().is_supabase_api_mode_enabled():
            key_result = _resolve_backend_main().create_key_result_via_supabase_api(
                objective_id=payload.objective_id,
                title=payload.title,
                description=payload.description,
                target_value=payload.target_value,
                unit=payload.unit,
                initiative_tags=_normalize_tags(payload.initiative_tags),
                weight=payload.weight,
                actor_username=actor,
            )
        else:
            key_result = _resolve_backend_main().create_key_result(
                objective_id=payload.objective_id,
                title=payload.title,
                description=payload.description,
                target_value=payload.target_value,
                unit=payload.unit,
                initiative_tags=_normalize_tags(payload.initiative_tags),
                weight=payload.weight,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = _node_view_from_obj("KEY_RESULT", key_result)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


def api_create_task(
    payload: TaskCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "tasks.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("TASK", replay)
    try:
        if _resolve_backend_main().is_supabase_api_mode_enabled():
            task = _resolve_backend_main().create_task_via_supabase_api(
                key_result_id=payload.key_result_id,
                title=payload.title,
                description=payload.description,
                estimated_minutes=payload.estimated_minutes,
                start_date=payload.start_date,
                deadline=payload.deadline,
                assignee_id=payload.assignee_id,
                actor_username=actor,
            )
        else:
            task = _resolve_backend_main().create_task(
                key_result_id=payload.key_result_id,
                title=payload.title,
                description=payload.description,
                estimated_minutes=payload.estimated_minutes,
                start_date=payload.start_date,
                deadline=payload.deadline,
                assignee_id=payload.assignee_id,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = _node_view_from_obj("TASK", task)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


_NODE_UPDATE_SCHEMAS = {
    "GOAL": GoalUpdateRequest,
    "OBJECTIVE": ObjectiveUpdateRequest,
    "KEY_RESULT": KeyResultUpdateRequest,
    "TASK": TaskUpdateRequest,
}


def api_update_node(
    node_type: str,
    node_id: int,
    payload: NodeUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    normalized_type = _normalize_node_type(node_type)
    schema_cls: Type[BaseModel] | None = cast(
        Type[BaseModel] | None, _NODE_UPDATE_SCHEMAS.get(normalized_type)
    )
    if schema_cls and payload.updates:
        try:
            validated = schema_cls.model_validate(payload.updates)
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        validated_updates = validated.model_dump(exclude_unset=True)
    else:
        validated_updates = dict(payload.updates)
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    updates = _normalize_updates(normalized_type, validated_updates)
    if is_supabase_api_mode_enabled():
        scope = _resolve_scope_for_actor(actor)
        owner_id = _resolve_goal_owner_id_for_node_via_supabase(
            node_type=normalized_type,
            node_id=int(node_id),
            actor=actor,
        )
        if owner_id is not None:
            _require_allowed_user_id(scope, int(owner_id))

    try:
        if is_supabase_api_mode_enabled():
            node = update_node_via_supabase_api(
                node_type=normalized_type,
                node_id=int(node_id),
                updates=updates,
            )
        else:
            if normalized_type == "GOAL":
                from backend_app import main as main_module

                node = main_module.update_goal(node_id, actor_username=actor, **updates)
            elif normalized_type == "OBJECTIVE":
                from backend_app import main as main_module

                node = main_module.update_objective(node_id, actor_username=actor, **updates)
            elif normalized_type == "KEY_RESULT":
                from backend_app import main as main_module

                node = main_module.update_key_result(node_id, actor_username=actor, **updates)
            else:
                # Keep task mutation patchable by test via backend_app.main.update_task.
                from backend_app import main as main_module

                node = main_module.update_task(
                    node_id, actor_username=actor, **updates
                )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    return _node_view_from_obj(normalized_type, node)


def api_delete_node(
    node_type: str,
    node_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeDeleteResponse:
    normalized_type = _normalize_node_type(node_type)
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    if is_supabase_api_mode_enabled():
        scope = _resolve_scope_for_actor(actor)
        owner_id = _resolve_goal_owner_id_for_node_via_supabase(
            node_type=normalized_type,
            node_id=int(node_id),
            actor=actor,
        )
        if owner_id is not None:
            _require_allowed_user_id(scope, int(owner_id))

    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_node_via_supabase_api(
                node_type=normalized_type,
                node_id=int(node_id),
            )
        else:
            if normalized_type == "GOAL":
                # Keep deletion dispatch patchable by test via backend_app.main.delete_goal.
                from backend_app import main as main_module

                deleted = main_module.delete_goal(node_id, actor_username=actor)
            elif normalized_type == "OBJECTIVE":
                from backend_app import main as main_module

                deleted = main_module.delete_objective(node_id, actor_username=actor)
            elif normalized_type == "KEY_RESULT":
                from backend_app import main as main_module

                deleted = main_module.delete_key_result(
                    node_id, actor_username=actor
                )
            else:
                from backend_app import main as main_module

                deleted = main_module.delete_task(node_id, actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found.")
    return NodeDeleteResponse(
        id=int(node_id),
        node_type=normalized_type,  # type: ignore[arg-type]
        deleted=True,
    )


def api_create_user(
    payload: UserCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    try:
        if _resolve_backend_main().is_supabase_api_mode_enabled():
            user = _resolve_backend_main().create_user_via_supabase_api(
                username=payload.username,
                password=payload.password,
                role=_coerce_enum(payload.role, UserRole, field_name="role"),
                display_name=payload.display_name,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                must_change_password=payload.must_change_password,
                actor_username=actor,
            )
        else:
            user = _resolve_backend_main().create_user(
                username=payload.username,
                password=payload.password,
                role=_coerce_enum(payload.role, UserRole, field_name="role"),
                display_name=payload.display_name,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                must_change_password=payload.must_change_password,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _user_view_from_obj(user)


def api_update_user(
    user_id: int,
    payload: UserUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    role = None
    if payload.role is not None:
        role = _coerce_enum(payload.role, UserRole, field_name="role")
    try:
        if is_supabase_api_mode_enabled():
            user = update_user_via_supabase_api(
                user_id=int(user_id),
                display_name=payload.display_name,
                role=role,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                is_active=payload.is_active,
                actor_username=actor,
            )
        else:
            user = update_user(
                user_id=int(user_id),
                display_name=payload.display_name,
                role=role,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                is_active=payload.is_active,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_view_from_obj(user)


def api_reset_user_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserPasswordResetResponse:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            reset_ok = reset_user_password_via_supabase_api(
                user_id=int(user_id),
                new_password=payload.new_password,
                require_change=bool(payload.require_change),
                actor_username=actor,
            )
        else:
            reset_ok = reset_user_password(
                user_id=int(user_id),
                new_password=payload.new_password,
                require_change=bool(payload.require_change),
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not reset_ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserPasswordResetResponse(user_id=int(user_id), reset=True)


def api_create_cycle(
    payload: CycleCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_or_manager_actor_scope(actor)
    # Per-manager cycle model: when a manager creates a cycle, ownership is
    # anchored on the manager themselves regardless of the form value sent
    # (mirrors the SQL path's behavior in crud_cycle_helpers). Admins may
    # still pick an explicit owner.
    scope = _resolve_scope_for_actor(actor)
    actor_id_int = int(scope.get("actor_id") or 0)
    is_admin_actor = bool(scope.get("is_admin", False))
    requested_owner = payload.owner_manager_id
    effective_owner = requested_owner if is_admin_actor else actor_id_int
    try:
        if is_supabase_api_mode_enabled():
            cycle = create_cycle_via_supabase_api(
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=effective_owner,
                actor_username=actor,
            )
        else:
            cycle = create_cycle(
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=effective_owner,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _cycle_view_from_obj(cycle)


def api_update_cycle(
    cycle_id: int,
    payload: CycleUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_or_manager_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            cycle = update_cycle_via_supabase_api(
                cycle_id=int(cycle_id),
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=payload.owner_manager_id,
                actor_username=actor,
            )
        else:
            cycle = update_cycle(
                cycle_id=int(cycle_id),
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=payload.owner_manager_id,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return _cycle_view_from_obj(cycle)


def api_delete_cycle(
    cycle_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_or_manager_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_cycle_via_supabase_api(cycle_id=int(cycle_id))
        else:
            deleted = delete_cycle(int(cycle_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return CycleDeleteResponse(id=int(cycle_id), deleted=True)


def api_create_team(
    payload: TeamCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            team = create_team_via_supabase_api(
                name=payload.name,
                description=payload.description,
                actor_username=actor,
            )
        else:
            team = create_team(
                name=payload.name,
                description=payload.description,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _team_view_from_obj(team)


def api_update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    try:
        if is_supabase_api_mode_enabled():
            team = update_team_via_supabase_api(
                team_id=int(team_id),
                updates=updates,
                actor_username=actor,
            )
        else:
            team = update_team(
                int(team_id),
                actor_username=actor,
                **updates,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    return _team_view_from_obj(team)


def api_delete_team(
    team_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_team_via_supabase_api(
                team_id=int(team_id),
                actor_username=actor,
            )
        else:
            deleted = delete_team(int(team_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found.")
    return TeamDeleteResponse(id=int(team_id), deleted=True)
