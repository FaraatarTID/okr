"""Health engine helpers for Atlas status/state computation."""

from __future__ import annotations

import logging
from typing import Any

from src.domain.lifecycle import LifecycleState, STATE_ICONS
from src.domain.scoring import (
    calculate_kr_score,
    calculate_objective_score,
    get_score_color_band,
    get_score_label,
)
from src.ui import atlas_logic_helpers


def _non_active_state_health(state: Any) -> dict[str, Any]:
    icon = STATE_ICONS.get(state, "")
    status_label = f"{icon} {state.value.title()}" if icon else state.value.title()
    kind = "inherited"
    if state == LifecycleState.GRADING:
        kind = "risk"
    elif state == LifecycleState.ARCHIVED:
        kind = "on_track"

    return {
        "kind": kind,
        "reason": status_label,
        "status_label": status_label,
        "source": "status_label",
        "needs_attention": state == LifecycleState.GRADING,
    }


def _resolve_task_status_label(
    *, node: Any, progress: int, logger: logging.Logger
) -> tuple[str, str]:
    task_status = str(
        getattr(getattr(node, "status", None), "value", getattr(node, "status", ""))
    ).lower()
    if task_status == "done":
        return "Done", "task_status"
    if task_status == "in_progress" and progress <= 0:
        return "In progress", "task_status"

    deadline = getattr(node, "deadline", None)
    if deadline is not None:
        try:
            from src.utils.deadline_utils import get_deadline_status

            _, status_label, _ = get_deadline_status(node)
            if status_label:
                return str(status_label), "deadline_status"
        except Exception as exc:
            logger.debug(
                "Failed to compute deadline health for node '%s': %s",
                getattr(node, "id", None),
                exc,
            )

    if progress >= 100:
        return "Done", "progress"
    if progress <= 0:
        return "Not started", "progress"
    return "In progress", "progress"


def _key_result_health(meta: dict[str, Any]) -> dict[str, Any]:
    node = meta.get("node")
    ai_warnings = [
        str(w).lower() for w in atlas_logic_helpers.atlas_ai_deadline_warnings(meta)
    ]
    if ai_warnings:
        if any("overdue" in warning for warning in ai_warnings):
            return {
                "kind": "overdue",
                "reason": "Needs care",
                "status_label": "Overdue (AI)",
                "source": "ai_deadline_warning",
                "needs_attention": True,
            }
        if any("risk" in warning for warning in ai_warnings):
            return {
                "kind": "risk",
                "reason": "Needs care",
                "status_label": "At risk (AI)",
                "source": "ai_deadline_warning",
                "needs_attention": True,
            }

    score = calculate_kr_score(
        current=getattr(node, "current_value", 0.0),
        target=getattr(node, "target_value", 100.0),
        start=getattr(node, "start_value", 0.0),
        metric_type=getattr(node, "metric_type", "numeric"),
    )
    score_label = get_score_label(score)
    if score <= 0.3:
        kind = "overdue"
    elif score <= 0.7:
        kind = "risk"
    elif score <= 0.9:
        kind = "on_track"
    else:
        kind = "done"

    return {
        "kind": kind,
        "reason": score_label,
        "status_label": f"Score: {score:.2f} ({score_label})",
        "source": "normalized_score",
        "needs_attention": kind in {"overdue", "risk"},
    }


def _objective_health(meta: dict[str, Any]) -> dict[str, Any] | None:
    node = meta.get("node")
    if not (hasattr(node, "key_results") and node.key_results):
        return None

    kr_scores = [
        calculate_kr_score(
            kr.current_value,
            kr.target_value,
            kr.start_value,
            kr.metric_type,
        )
        for kr in node.key_results
    ]
    kr_weights = [kr.weight for kr in node.key_results]
    weighted = atlas_logic_helpers.atlas_is_weighted_mode(
        getattr(node, "score_mode", None)
    )
    obj_score = calculate_objective_score(
        kr_scores,
        kr_weights if weighted else None,
        weighted=weighted,
    )
    score_label = get_score_label(obj_score)
    if obj_score <= 0.3:
        kind = "overdue"
    elif obj_score <= 0.7:
        kind = "risk"
    elif obj_score <= 0.9:
        kind = "on_track"
    else:
        kind = "done"

    return {
        "kind": kind,
        "reason": score_label,
        "status_label": f"Score: {obj_score:.2f} ({score_label})",
        "source": "normalized_score",
        "needs_attention": kind in {"overdue", "risk"},
    }


def _derive_kind_from_status_label(
    *, status_label: str, source: str, progress: int
) -> tuple[str | None, str]:
    if progress >= 100:
        return "done", source

    status_lower = str(status_label).lower()
    if "done" in status_lower or "complete" in status_lower:
        return "done", "status_label" if source == "progress" else source
    if "overdue" in status_lower:
        return "overdue", "status_label" if source == "progress" else source
    if "risk" in status_lower:
        return "risk", "status_label" if source == "progress" else source
    return None, source


def _resolve_default_status_label(*, progress: int) -> str:
    if progress >= 100:
        return "Done"
    if progress < 40:
        return "Needs attention"
    return "In progress"


def _resolve_inherited_kind(
    *,
    meta: dict[str, Any],
    index: dict[str, Any] | None,
    visited_refs: set[str],
    memo: dict[str, Any] | None,
    logger: logging.Logger,
) -> tuple[str | None, str]:
    if index is None:
        return None, "progress"

    source = "progress"
    for child_ref in list(meta.get("children") or []):
        if child_ref in visited_refs:
            continue
        child_meta = index.get(child_ref)
        if not child_meta:
            continue
        child_health = atlas_health_state(
            child_meta,
            index=index,
            _visited_refs=visited_refs,
            _memo=memo,
            logger=logger,
        )
        if child_health.get("needs_attention"):
            return "inherited", "inherited_rollup"
    return None, source


def atlas_health_state(
    meta: dict[str, Any],
    index: dict[str, Any] | None = None,
    _visited_refs=None,
    _memo=None,
    *,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Canonical Atlas health engine for map/inspector status surfaces."""
    log = logger or logging.getLogger(__name__)
    meta_ref = meta.get("ref")
    if _memo is not None and meta_ref and meta_ref in _memo:
        return _memo[meta_ref]

    progress = int(meta.get("progress", 0) or 0)
    node_type = meta.get("type")
    node = meta.get("node")
    state = getattr(node, "state", LifecycleState.ACTIVE)

    if state != LifecycleState.ACTIVE:
        return _non_active_state_health(state)

    if node_type == "KEY_RESULT":
        return _key_result_health(meta)
    if node_type == "OBJECTIVE":
        objective_result = _objective_health(meta)
        if objective_result is not None:
            return objective_result

    status_label = None
    source = "progress"
    if node_type == "TASK":
        status_label, source = _resolve_task_status_label(
            node=node,
            progress=progress,
            logger=log,
        )

    if status_label is None:
        status_label = _resolve_default_status_label(progress=progress)

    kind, source = _derive_kind_from_status_label(
        status_label=status_label,
        source=source,
        progress=progress,
    )

    if kind is None:
        visited_refs = set(_visited_refs or [])
        if meta_ref:
            visited_refs.add(meta_ref)
        kind, inherited_source = _resolve_inherited_kind(
            meta=meta,
            index=index,
            visited_refs=visited_refs,
            memo=_memo,
            logger=log,
        )
        if kind is not None:
            source = inherited_source

    if kind is None:
        kind = "low_progress" if progress < 40 else "on_track"

    if kind == "done":
        reason = "Complete"
    elif kind in {"overdue", "risk", "inherited", "low_progress"}:
        reason = "Needs care"
    else:
        reason = "On track"

    result = {
        "kind": kind,
        "reason": reason,
        "status_label": status_label,
        "source": source,
        "needs_attention": kind in {"overdue", "risk", "inherited", "low_progress"},
    }
    if _memo is not None and meta_ref:
        _memo[meta_ref] = result
    return result


def atlas_health_index(index: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(index, dict) or not index:
        return {}
    memo = {}
    health_by_ref = {}
    for ref, meta in index.items():
        if not isinstance(meta, dict):
            continue
        health_by_ref[ref] = atlas_health_state(meta, index=index, _memo=memo)
    return health_by_ref


def _score_for_goal_like_meta(meta: dict[str, Any]) -> float:
    node = meta.get("node")
    node_type = meta.get("type")

    if node_type == "KEY_RESULT":
        return calculate_kr_score(
            getattr(node, "current_value", 0.0),
            getattr(node, "target_value", 100.0),
            getattr(node, "start_value", 0.0),
            getattr(node, "metric_type", "NUMERIC"),
        )

    if node_type == "OBJECTIVE":
        krs = getattr(node, "key_results", [])
        if not krs:
            return 0.0
        kr_scores = [
            calculate_kr_score(
                getattr(kr, "current_value", 0.0),
                getattr(kr, "target_value", 100.0),
                getattr(kr, "start_value", 0.0),
                getattr(kr, "metric_type", "NUMERIC"),
            )
            for kr in krs
        ]
        kr_weights = [getattr(kr, "weight", 1.0) for kr in krs]
        weighted = atlas_logic_helpers.atlas_is_weighted_mode(
            getattr(node, "score_mode", None)
        )
        return calculate_objective_score(
            kr_scores,
            kr_weights if weighted else None,
            weighted=weighted,
        )

    objectives = getattr(node, "objectives", [])
    obj_scores = []
    for objective in objectives:
        krs = getattr(objective, "key_results", [])
        if not krs:
            continue
        kr_scores = [
            calculate_kr_score(
                getattr(kr, "current_value", 0.0),
                getattr(kr, "target_value", 100.0),
                getattr(kr, "start_value", 0.0),
                getattr(kr, "metric_type", "NUMERIC"),
            )
            for kr in krs
        ]
        kr_weights = [getattr(kr, "weight", 1.0) for kr in krs]
        weighted = atlas_logic_helpers.atlas_is_weighted_mode(
            getattr(objective, "score_mode", None)
        )
        obj_scores.append(
            calculate_objective_score(
                kr_scores,
                kr_weights if weighted else None,
                weighted=weighted,
            )
        )
    return (sum(obj_scores) / len(obj_scores)) if obj_scores else 0.0


def atlas_health_fill_color(health, progress: int, meta=None) -> str:
    kind = str((health or {}).get("kind") or "")
    if meta and meta.get("type") in ["GOAL", "OBJECTIVE", "KEY_RESULT"]:
        score = _score_for_goal_like_meta(meta)
        band = get_score_color_band(score)
        mapping = {
            "atlas-score-band-red": "#fce7e2",
            "atlas-score-band-yellow": "#fff1de",
            "atlas-score-band-green": "#e8f8f3",
            "atlas-score-band-blue": "#e0f2fe",
        }
        return mapping.get(band, "#e5d6bb")

    if kind in {"overdue", "risk", "inherited", "low_progress"}:
        return "#c36d27"
    if kind == "done" or int(progress or 0) >= 100:
        return "#b5becb"
    return "#e5d6bb"
