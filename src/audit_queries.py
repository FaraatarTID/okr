"""Reusable read helpers for querying audit events."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any, Optional, cast

from sqlalchemy import func
from sqlmodel import Session, select


from src.models import AuditEvent
from src.utils.time_utils import utc_now_naive


def _normalize_optional_text(value: object) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _normalize_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def build_audit_event_query(
    *,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    actor: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    actor_team_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_owner_id: Optional[int] = None,
    target_team_id: Optional[int] = None,
    result: Optional[str] = None,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    created_after=None,
    created_before=None,
    newest_first: bool = True,
):
    statement = select(AuditEvent)
    if action is not None:
        statement = statement.where(
            AuditEvent.action == _normalize_optional_text(action)
        )
    if entity is not None:
        statement = statement.where(
            AuditEvent.entity == _normalize_optional_text(entity)
        )
    if actor is not None:
        statement = statement.where(AuditEvent.actor == _normalize_optional_text(actor))
    if actor_user_id is not None:
        statement = statement.where(
            AuditEvent.actor_user_id == _normalize_optional_int(actor_user_id)
        )
    if actor_role is not None:
        statement = statement.where(
            AuditEvent.actor_role == _normalize_optional_text(actor_role)
        )
    if actor_team_id is not None:
        statement = statement.where(
            AuditEvent.actor_team_id == _normalize_optional_int(actor_team_id)
        )
    if target_type is not None:
        statement = statement.where(
            AuditEvent.target_type == _normalize_optional_text(target_type)
        )
    if target_id is not None:
        statement = statement.where(
            AuditEvent.target_id == _normalize_optional_int(target_id)
        )
    if target_owner_id is not None:
        statement = statement.where(
            AuditEvent.target_owner_id == _normalize_optional_int(target_owner_id)
        )
    if target_team_id is not None:
        statement = statement.where(
            AuditEvent.target_team_id == _normalize_optional_int(target_team_id)
        )
    if result is not None:
        statement = statement.where(
            AuditEvent.result == _normalize_optional_text(result)
        )
    if correlation_id is not None:
        statement = statement.where(
            AuditEvent.correlation_id == _normalize_optional_text(correlation_id)
        )
    if request_id is not None:
        statement = statement.where(
            AuditEvent.request_id == _normalize_optional_text(request_id)
        )
    if created_after is not None:
        statement = statement.where(AuditEvent.created_at >= created_after)
    if created_before is not None:
        statement = statement.where(AuditEvent.created_at <= created_before)

    created_at = cast(Any, AuditEvent.created_at)
    event_id = cast(Any, AuditEvent.id)
    order_column = created_at.desc() if newest_first else created_at.asc()
    return statement.order_by(
        order_column, event_id.desc() if newest_first else event_id.asc()
    )


def list_audit_events(session: Session, **filters) -> list[AuditEvent]:
    statement = build_audit_event_query(**filters)
    return list(session.exec(statement).all())


def count_audit_events(session: Session, **filters) -> int:
    statement = build_audit_event_query(**filters)
    count_statement = select(func.count()).select_from(statement.subquery())
    return int(session.exec(count_statement).one() or 0)


def _aggregate_counts(rows: list[AuditEvent], attr: str) -> list[dict[str, object]]:
    counter: Counter[object] = Counter()
    for row in rows:
        value = getattr(row, attr, None)
        if value is None:
            continue
        counter[value] += 1
    items = []
    for value, count in counter.items():
        items.append({"value": value, "count": int(count)})
    items.sort(key=lambda item: (-int(cast(int, item["count"])), str(item["value"])))
    return items


def serialize_audit_event(event: AuditEvent) -> dict[str, object]:
    return {
        "id": int(getattr(event, "id", 0) or 0),
        "actor": getattr(event, "actor", None),
        "actor_user_id": getattr(event, "actor_user_id", None),
        "actor_role": getattr(event, "actor_role", None),
        "actor_team_id": getattr(event, "actor_team_id", None),
        "action": getattr(event, "action", None),
        "entity": getattr(event, "entity", None),
        "result": getattr(event, "result", None),
        "target_type": getattr(event, "target_type", None),
        "target_id": getattr(event, "target_id", None),
        "target_owner_id": getattr(event, "target_owner_id", None),
        "target_team_id": getattr(event, "target_team_id", None),
        "correlation_id": getattr(event, "correlation_id", None),
        "request_id": getattr(event, "request_id", None),
        "created_at": getattr(event, "created_at", None),
    }


def summarize_audit_events(
    session: Session,
    *,
    days: int = 30,
    recent_limit: int = 20,
    **filters,
) -> dict[str, object]:
    safe_days = max(1, int(days or 30))
    safe_recent_limit = max(1, min(100, int(recent_limit or 20)))
    cutoff = utc_now_naive() - timedelta(days=safe_days)
    query_filters = dict(filters or {})
    query_filters["created_after"] = cutoff

    rows = list(session.exec(build_audit_event_query(**query_filters)).all())
    recent_rows = rows[:safe_recent_limit]

    success_count = sum(
        1 for row in rows if str(getattr(row, "result", "")).lower() == "success"
    )
    failure_count = sum(
        1 for row in rows if str(getattr(row, "result", "")).lower() == "failure"
    )
    latest_event_at = rows[0].created_at if rows else None

    return {
        "window_days": safe_days,
        "recent_limit": safe_recent_limit,
        "total_events": len(rows),
        "success_events": success_count,
        "failure_events": failure_count,
        "latest_event_at": latest_event_at,
        "by_actor_role": _aggregate_counts(rows, "actor_role"),
        "by_actor_team_id": _aggregate_counts(rows, "actor_team_id"),
        "by_target_type": _aggregate_counts(rows, "target_type"),
        "by_entity": _aggregate_counts(rows, "entity"),
        "by_action": _aggregate_counts(rows, "action"),
        "recent_events": [serialize_audit_event(event) for event in recent_rows],
    }
