"""Supabase HTTPS API-only runtime helpers (workflow slice).

Operational and workflow mutation helpers extracted from the main Supabase API module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import types
import logging

import bcrypt

from src.domain.scoring import calculate_kr_score
from src.crud import _ALLOWED_EXPERIMENT_UPDATE_FIELDS
from src.services.supabase_api_mode_transport import (
    SupabaseTransportError,
    _coerce_payload_value,
    _coerce_float,
    _parse_dt,
    _recalculate_objective_progress_via_supabase,
    _request_json_with_method,
    _rest_select,
    _rest_insert,
    _rest_update,
    _rest_delete,
    _as_int,
    _date_only_iso,
    _utc_now_iso,
    _cycle_owner_column_supported,
    _cycle_select_fields,
    _role_for_storage,
    _normalize_user_row_role,
)
from src.services.supabase_api_mode_read import _rest_rpc

logger = logging.getLogger(__name__)


def start_timer_via_supabase_api(*, task_id: int, actor_username: str):
    status, task_rows = _rest_select(
        "task",
        query={"id": f"eq.{int(task_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (timer.start/task): {status}")
    if not task_rows:
        raise ValueError("Task not found.")
    status, active_rows = _rest_select(
        "work_log",
        query={
            "task_id": f"eq.{int(task_id)}",
            "end_time": "is.null",
            "select": "id,task_id,start_time",
            "limit": "1",
            "order": "start_time.desc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (timer.start/work_log): {status}")
    if active_rows:
        row = active_rows[0]
        return types.SimpleNamespace(
            id=row.get("id"),
            task_id=row.get("task_id"),
            start_time=row.get("start_time"),
        )
    status, rows = _rest_insert(
        "work_log",
        payload={
            "task_id": int(task_id),
            "start_time": _utc_now_iso(),
            # duration_minutes is NOT NULL with no DB default; the ORM applies
            # a Python-side 0.0 default that PostgREST does not see.
            "duration_minutes": 0,
            "summary": None,
            "note": None,
        },
    )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (timer.start/insert): {status}")
    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        task_id=row.get("task_id"),
        start_time=row.get("start_time"),
    )


def stop_timer_via_supabase_api(*, task_id: int, summary: Optional[str], user_id: str):
    _ = user_id
    status, active_rows = _rest_select(
        "work_log",
        query={
            "task_id": f"eq.{int(task_id)}",
            "end_time": "is.null",
            "select": "id,task_id,start_time",
            "limit": "1",
            "order": "start_time.desc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (timer.stop/select): {status}")
    if not active_rows:
        return None
    row = active_rows[0]
    work_log_id = _as_int(row.get("id"), 0)
    start_dt = _parse_dt(row.get("start_time")) or datetime.now(timezone.utc)
    end_dt = datetime.now(timezone.utc)
    # Round to whole minutes for parity with the ORM timer path
    # (crud_timer_helpers stores int minutes, not fractional durations).
    duration = max(0, int((end_dt - start_dt).total_seconds() / 60.0))
    status, updated = _rest_update(
        "work_log",
        match_query={"id": f"eq.{work_log_id}"},
        payload={
            "end_time": end_dt.isoformat(),
            "duration_minutes": duration,
            "summary": (str(summary).strip() if summary is not None else None),
        },
    )
    if status >= 400 or not updated:
        raise ValueError(f"Supabase API error (timer.stop/update): {status}")

    # Fetch task to update total_time_spent and auto-compute progress
    _, task_rows = _rest_select(
        "task",
        query={
            "id": f"eq.{int(task_id)}",
            "select": "id,total_time_spent,estimated_minutes",
        },
    )
    if task_rows:
        t = task_rows[0]
        new_total = int(t.get("total_time_spent") or 0) + int(duration)
        estimated = int(t.get("estimated_minutes") or 0)
        if estimated > 0:
            new_progress = min(999, max(0, int(new_total / estimated * 100)))
        else:
            new_progress = min(999, max(0, new_total))
        _rest_update(
            "task",
            match_query={"id": f"eq.{int(task_id)}"},
            payload={
                "total_time_spent": new_total,
                "progress": new_progress,
            },
        )

    u = updated[0]
    return types.SimpleNamespace(
        id=u.get("id"),
        task_id=u.get("task_id"),
        duration_minutes=u.get("duration_minutes"),
        start_time=u.get("start_time"),
        end_time=u.get("end_time"),
        summary=u.get("summary"),
    )


def create_check_in_via_supabase_api(
    *,
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type: Optional[Any] = None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
):
    _ = actor_username
    status, krs = _rest_select(
        "key_result",
        query={
            "id": f"eq.{int(kr_id)}",
            "select": "id,start_value,target_value,current_value,metric_type",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (check_in/key_result): {status}")
    if not krs:
        raise ValueError("Key result not found.")
    payload = {
        "key_result_id": int(kr_id),
        "value": float(value),
        "confidence_score": int(confidence),
        "comment": str(comment or ""),
        "variation_type": _coerce_payload_value(variation_type),
        "special_cause_note": special_cause_note,
        "experiment_id": int(experiment_id) if experiment_id is not None else None,
        "created_at": _utc_now_iso(),
    }
    status, rows = _rest_insert("check_in", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (check_in/insert): {status}")

    kr_row = krs[0]
    score = calculate_kr_score(
        current=float(value),
        target=_coerce_float(kr_row.get("target_value"), 100.0),
        start=_coerce_float(kr_row.get("start_value"), 0.0),
        metric_type=str(kr_row.get("metric_type") or "numeric"),
    )
    new_progress = max(0, min(100, int(round(score * 100))))

    _rest_update(
        "key_result",
        match_query={"id": f"eq.{int(kr_id)}"},
        payload={"current_value": float(value), "progress": new_progress},
    )

    objective_id = None
    kr_obj_status, kr_obj_rows = _rest_select(
        "key_result",
        query={"id": f"eq.{int(kr_id)}", "select": "objective_id", "limit": "1"},
    )
    if kr_obj_status < 400 and kr_obj_rows:
        objective_id = _as_int(kr_obj_rows[0].get("objective_id"), 0)

    if objective_id is not None and objective_id > 0:
        _recalculate_objective_progress_via_supabase(objective_id)

    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        key_result_id=row.get("key_result_id"),
        value=row.get("value"),
        confidence_score=row.get("confidence_score"),
        comment=row.get("comment"),
        variation_type=row.get("variation_type"),
        special_cause_note=row.get("special_cause_note"),
        experiment_id=row.get("experiment_id"),
        created_at=row.get("created_at"),
    )


def create_experiment_via_supabase_api(
    *,
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at: Optional[datetime] = None,
    expected_effect_direction: Optional[Any] = None,
    expected_effect_size: Optional[float] = None,
):
    payload = {
        "key_result_id": int(key_result_id),
        "cycle_id": int(cycle_id),
        "created_by": str(actor_username or "").strip(),
        "hypothesis": str(hypothesis or ""),
        "change_description": str(change_description or ""),
        "start_at": (start_at.isoformat() if start_at else _utc_now_iso()),
        "status": "PLANNED",
        "expected_effect_direction": _coerce_payload_value(expected_effect_direction),
        "expected_effect_size": expected_effect_size,
    }
    status, rows = _rest_insert("experiment", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (experiment/create): {status}")
    return types.SimpleNamespace(**rows[0])


def get_experiment_via_supabase_api(
    *, experiment_id: int
) -> types.SimpleNamespace | None:
    status, rows = _rest_select(
        "experiment",
        query={"id": f"eq.{int(experiment_id)}", "select": "*", "limit": "1"},
    )
    if status >= 400 or not rows:
        if status >= 400:
            raise ValueError(f"Supabase API error (experiment/get): {status}")
        return None
    return types.SimpleNamespace(**rows[0])


def update_experiment_via_supabase_api(
    *, experiment_id: int, updates: dict[str, Any], actor_username: str
):
    _ = actor_username
    # Filter to allowed fields to prevent mass-assignment
    allowed = _ALLOWED_EXPERIMENT_UPDATE_FIELDS
    filtered = {k: v for k, v in dict(updates or {}).items() if k in allowed}
    payload = {k: _coerce_payload_value(v) for k, v in filtered.items()}
    status, rows = _rest_update(
        "experiment",
        match_query={"id": f"eq.{int(experiment_id)}"},
        payload=payload,
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (experiment/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def close_experiment_via_supabase_api(
    *,
    experiment_id: int,
    decision: Any,
    rationale: str,
    actor_username: str,
):
    _ = actor_username
    status, rows = _rest_update(
        "experiment",
        match_query={"id": f"eq.{int(experiment_id)}"},
        payload={
            "status": "DECIDED",
            "decision": _coerce_payload_value(decision),
            "decision_rationale": str(rationale or ""),
            "end_at": _utc_now_iso(),
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (experiment/close): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def create_retrospective_via_supabase_api(
    *,
    user_id: int,
    cycle_id: Optional[int],
    week_start_date: datetime,
    content: str,
    sentiment: Optional[str],
    actor_username: str,
):
    _ = actor_username
    status, existing = _rest_select(
        "retrospective",
        query={
            "user_id": f"eq.{int(user_id)}",
            "week_start_date": f"eq.{week_start_date.isoformat()}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (retro/select): {status}")
    if existing:
        status, rows = _rest_update(
            "retrospective",
            match_query={"id": f"eq.{_as_int(existing[0].get('id'), 0)}"},
            payload={
                "content": str(content or ""),
                "sentiment": sentiment,
                "created_at": _utc_now_iso(),
            },
        )
    else:
        status, rows = _rest_insert(
            "retrospective",
            payload={
                "user_id": int(user_id),
                "cycle_id": int(cycle_id) if cycle_id is not None else None,
                "week_start_date": week_start_date.isoformat(),
                "content": str(content or ""),
                "sentiment": sentiment,
                "created_at": _utc_now_iso(),
            },
        )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (retro/create): {status}")
    return types.SimpleNamespace(**rows[0])


def upsert_retro_experiment_outcome_via_supabase_api(
    *,
    retrospective_id: int,
    experiment_id: int,
    decision: Any,
    rationale: Optional[str],
    actor_username: str,
):
    _ = actor_username
    status, existing = _rest_select(
        "retro_experiment_outcome",
        query={
            "retrospective_id": f"eq.{int(retrospective_id)}",
            "experiment_id": f"eq.{int(experiment_id)}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (retro_outcome/select): {status}")
    payload = {
        "retrospective_id": int(retrospective_id),
        "experiment_id": int(experiment_id),
        "decision": _coerce_payload_value(decision),
        "rationale": rationale,
    }
    if existing:
        status, rows = _rest_update(
            "retro_experiment_outcome",
            match_query={"id": f"eq.{_as_int(existing[0].get('id'), 0)}"},
            payload=payload,
        )
    else:
        status, rows = _rest_insert("retro_experiment_outcome", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (retro_outcome/upsert): {status}")
    return types.SimpleNamespace(**rows[0])


def create_weekly_plan_via_supabase_api(
    *,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    p1: str,
    p2: Optional[str] = None,
    p3: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    if not str(p1 or "").strip():
        raise ValueError("Priority #1 is required.")
    if start_date >= end_date:
        raise ValueError("Week start_date must be before end_date.")

    status, existing = _rest_select(
        "weekly_plan",
        query={
            "user_id": f"eq.{int(user_id)}",
            "week_start_date": f"eq.{start_date.isoformat()}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (weekly_plan/select): {status}")
    payload = {
        "user_id": int(user_id),
        "week_start_date": start_date.isoformat(),
        "week_end_date": end_date.isoformat(),
        "priority_1": str(p1 or ""),
        "priority_2": p2,
        "priority_3": p3,
        "is_active": True,
        "created_at": _utc_now_iso(),
    }
    if existing:
        status, rows = _rest_update(
            "weekly_plan",
            match_query={"id": f"eq.{_as_int(existing[0].get('id'), 0)}"},
            payload={k: v for k, v in payload.items() if k != "created_at"},
        )
    else:
        status, rows = _rest_insert("weekly_plan", payload=payload)
    if status >= 400 or not rows:
        detail = ""
        if isinstance(rows, dict):
            detail = rows.get("message", rows.get("hint", str(rows)))
        raise ValueError(
            f"Supabase API error (weekly_plan/upsert): {status} {detail}".strip()
        )
    return types.SimpleNamespace(**rows[0])


def create_alignment_via_supabase_api(
    *,
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
):
    if int(parent_id) == int(child_id):
        raise ValueError("Adding this alignment would create a circular dependency.")
    status, parent = _rest_select(
        "objective",
        query={"id": f"eq.{int(parent_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/parent): {status}")
    status, child = _rest_select(
        "objective",
        query={"id": f"eq.{int(child_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/child): {status}")
    if not parent or not child:
        raise ValueError("Target objectives not found.")

    status, existing = _rest_select(
        "alignment_edge",
        query={
            "parent_id": f"eq.{int(parent_id)}",
            "child_id": f"eq.{int(child_id)}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/select): {status}")
    if existing:
        return types.SimpleNamespace(**existing[0])

    status, rows = _rest_insert(
        "alignment_edge",
        payload={
            "parent_id": int(parent_id),
            "child_id": int(child_id),
            "alignment_type": str(alignment_type or "SUPPORTS"),
            "created_by": str(actor_username or "").strip() or None,
            "created_at": _utc_now_iso(),
        },
    )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (alignment/create): {status}")
    return types.SimpleNamespace(**rows[0])


def delete_alignment_via_supabase_api(
    *, edge_id: int, actor_username: Optional[str] = None
) -> bool:
    _ = actor_username
    status, rows = _rest_select(
        "alignment_edge",
        query={"id": f"eq.{int(edge_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/delete/select): {status}")
    if not rows:
        return False
    status = _rest_delete("alignment_edge", match_query={"id": f"eq.{int(edge_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/delete): {status}")
    return True


def create_user_via_supabase_api(
    *,
    username: str,
    password: str,
    role: Any = "member",
    display_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    payload = {
        "username": str(username or "").strip(),
        "password_hash": password_hash,
        "display_name": display_name,
        "role": _role_for_storage(role),
        "manager_id": int(manager_id) if manager_id is not None else None,
        "team_id": int(team_id) if team_id is not None else None,
        "must_change_password": bool(must_change_password),
        "is_active": True,
        # The live DB has no server default for created_at (ORM default is
        # invisible to PostgREST), so it must be supplied explicitly.
        "created_at": _utc_now_iso(),
    }
    status, rows = _rest_insert("user", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (user/create): {status}")
    return types.SimpleNamespace(**_normalize_user_row_role(rows[0]))


def update_user_via_supabase_api(
    *,
    user_id: int,
    display_name: Optional[str] = None,
    role: Optional[Any] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    payload: dict[str, Any] = {}
    if display_name is not None:
        payload["display_name"] = display_name
    if role is not None:
        payload["role"] = _role_for_storage(role)
    if manager_id is not None:
        payload["manager_id"] = int(manager_id)
    if team_id is not None:
        payload["team_id"] = int(team_id)
    if is_active is not None:
        payload["is_active"] = bool(is_active)
    status, rows = _rest_update(
        "user",
        match_query={"id": f"eq.{int(user_id)}"},
        payload=payload,
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (user/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**_normalize_user_row_role(rows[0]))


def reset_user_password_via_supabase_api(
    *,
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    _ = actor_username
    password_hash = bcrypt.hashpw(
        new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    status, rows = _rest_update(
        "user",
        match_query={"id": f"eq.{int(user_id)}"},
        payload={
            "password_hash": password_hash,
            "must_change_password": bool(require_change),
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (user/reset_password): {status}")
    return bool(rows)


def create_cycle_via_supabase_api(
    *,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool = True,
    owner_manager_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    payload = {
        "title": str(title or "").strip(),
        "start_date": _date_only_iso(start_date),
        "end_date": _date_only_iso(end_date),
        "is_active": bool(is_active),
    }
    if _cycle_owner_column_supported():
        payload["owner_manager_id"] = (
            int(owner_manager_id) if owner_manager_id is not None else None
        )
    # Invariant: at most one active cycle. Activating a new cycle deactivates
    # all others in the same transactional sequence.
    if payload["is_active"]:
        _rest_update("cycle", match_query={"is_active": "eq.true"}, payload={"is_active": False})
    status, response = _request_json_with_method(
        "POST",
        "/rest/v1/cycle",
        body=payload,
        prefer_representation=True,
    )
    rows = (
        [row for row in response if isinstance(row, dict)]
        if isinstance(response, list)
        else []
    )
    if status >= 400 or not rows:
        raise ValueError(
            f"Supabase API error (cycle/create): {status} details={response}"
        )
    return types.SimpleNamespace(**rows[0])


def update_cycle_via_supabase_api(
    *,
    cycle_id: int,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool,
    owner_manager_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    # Guard: deactivating the only active cycle would leave the workspace
    # without a current period. Require activating another cycle instead.
    if not is_active:
        status, active_rows = _rest_select(
            "cycle",
            query={
                "is_active": "eq.true",
                "id": f"neq.{int(cycle_id)}",
                "select": "id",
                "limit": "1",
            },
        )
        if status < 400 and not active_rows:
            status2, own_rows = _rest_select(
                "cycle",
                query={
                    "id": f"eq.{int(cycle_id)}",
                    "select": "is_active",
                    "limit": "1",
                },
            )
            if (
                status2 < 400
                and own_rows
                and bool(own_rows[0].get("is_active"))
            ):
                raise ValueError(
                    "Cannot deactivate the only active cycle. "
                    "Activate another cycle first."
                )

    # Atomic activation path (preferred): fn_activate_cycle RPC deactivates all
    # other cycles and activates the target inside one DB transaction. Falls
    # back to two REST calls only when the RPC is missing (migration not yet
    # applied) — same 42883-only fallback contract as ritual.snapshot.
    if is_active:
        rpc_done = False
        try:
            status, payload = _rest_rpc(
                "fn_activate_cycle", {"p_cycle_id": int(cycle_id)}
            )
            if status < 400:
                rpc_done = True
            else:
                detail = ""
                code = ""
                if isinstance(payload, dict):
                    detail = str(payload.get("message") or payload.get("details") or "")
                    code = str(payload.get("code") or "")
                rpc_missing = status == 404 and (
                    code in {"42883", "PGRST202"} or "does not exist" in detail
                )
                if not rpc_missing:
                    raise ValueError(
                        f"Supabase API error (cycle/activate_rpc): {status} {detail}"
                    )
                # RPC missing -> fall through to the legacy two-call path.
        except SupabaseTransportError:
            raise

        if rpc_done:
            # Refresh full row after activation so callers get current fields.
            status, rows = _rest_select(
                "cycle",
                query={
                    "id": f"eq.{int(cycle_id)}",
                    "select": _cycle_select_fields(),
                    "limit": "1",
                },
            )
            if status >= 400 or not rows:
                raise ValueError(
                    f"Supabase API error (cycle/update refresh): {status}"
                )
            return types.SimpleNamespace(**rows[0])

        # Legacy fallback: deactivate others, then activate target.
        _rest_update(
            "cycle",
            match_query={"is_active": "eq.true"},
            payload={"is_active": False},
        )

    status, rows = _rest_update(
        "cycle",
        match_query={"id": f"eq.{int(cycle_id)}"},
        payload=(
            lambda: {
                "title": str(title or "").strip(),
                "start_date": _date_only_iso(start_date),
                "end_date": _date_only_iso(end_date),
                "is_active": bool(is_active),
                **(
                    {
                        "owner_manager_id": int(owner_manager_id)
                        if owner_manager_id is not None
                        else None
                    }
                    if _cycle_owner_column_supported()
                    else {}
                ),
            }
        )(),
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (cycle/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def delete_cycle_via_supabase_api(
    *, cycle_id: int, actor_username: Optional[str] = None
) -> bool:
    _ = actor_username
    status, rows = _rest_select(
        "cycle", query={"id": f"eq.{int(cycle_id)}", "select": "id", "limit": "1"}
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (cycle/delete/select): {status}")
    if not rows:
        return False
    status = _rest_delete("cycle", match_query={"id": f"eq.{int(cycle_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (cycle/delete): {status}")
    return True


