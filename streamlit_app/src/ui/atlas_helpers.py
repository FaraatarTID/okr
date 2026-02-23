"""Shared pure helpers for Atlas UI interactions."""

from __future__ import annotations

import ast
import json
import logging

from src.domain.lifecycle import LifecycleState, STATE_ICONS
from src.domain.scoring import (
    calculate_kr_score,
    calculate_objective_score,
    get_score_color_band,
    get_score_label,
)
from src.ui import atlas_selection_event_helpers

logger = logging.getLogger(__name__)


def _atlas_ai_progress_decision(
    current_progress,
    ai_score,
    max_delta: int = 25,
    allow_decrease: bool = False,
):
    """Policy gate for applying AI score to KR progress."""
    try:
        current_val = max(0, min(100, int(float(current_progress))))
    except Exception as exc:
        logger.debug("Invalid current_progress '%s': %s", current_progress, exc)
        current_val = 0
    try:
        if ai_score is None:
            raise ValueError("missing_ai_score")
        proposed_val = max(0, min(100, int(float(ai_score))))
    except Exception as exc:
        logger.debug("Invalid ai_score '%s': %s", ai_score, exc)
        return {
            "action": "skip",
            "reason": "missing_ai_score",
            "current_progress": current_val,
            "proposed_progress": None,
            "delta": None,
        }

    delta = int(proposed_val - current_val)
    bounded_delta = max(0, min(100, int(max_delta or 0)))

    if delta == 0:
        return {
            "action": "skip",
            "reason": "no_change",
            "current_progress": current_val,
            "proposed_progress": proposed_val,
            "delta": 0,
        }
    if delta < 0 and not bool(allow_decrease):
        return {
            "action": "skip",
            "reason": "decrease_blocked",
            "current_progress": current_val,
            "proposed_progress": proposed_val,
            "delta": delta,
        }
    if abs(delta) > bounded_delta:
        return {
            "action": "skip",
            "reason": "delta_cap",
            "current_progress": current_val,
            "proposed_progress": proposed_val,
            "delta": delta,
        }
    return {
        "action": "apply",
        "reason": "within_policy",
        "current_progress": current_val,
        "proposed_progress": proposed_val,
        "delta": delta,
    }


def _atlas_commit_target_minutes(
    preset_choice: str, custom_minutes: int | None = None
) -> int:
    preset = str(preset_choice or "25m")
    if preset == "50m":
        return 50
    if preset == "Custom":
        if custom_minutes is None:
            return 35
        return max(5, min(240, int(custom_minutes)))
    return 25


def _atlas_sprint_run_key(
    task_ref: str | None, target_minutes: int, started_at_epoch
) -> str | None:
    if not task_ref:
        return None
    try:
        target = int(target_minutes or 0)
    except Exception as exc:
        logger.debug("Invalid sprint target_minutes '%s': %s", target_minutes, exc)
        target = 0
    if target <= 0:
        return None
    try:
        started = int(float(started_at_epoch or 0))
    except Exception as exc:
        logger.debug("Invalid sprint started_at_epoch '%s': %s", started_at_epoch, exc)
        started = 0
    if started <= 0:
        return None
    return f"{task_ref}|{target}|{started}"


def _atlas_should_show_soft_reminder(
    elapsed_minutes: int,
    target_minutes: int,
    sprint_key: str | None,
    dismissed_key: str | None,
) -> bool:
    if not sprint_key:
        return False
    if dismissed_key == sprint_key:
        return False
    try:
        elapsed = int(elapsed_minutes or 0)
        target = int(target_minutes or 0)
    except Exception as exc:
        logger.debug(
            "Invalid reminder timing values elapsed='%s' target='%s': %s",
            elapsed_minutes,
            target_minutes,
            exc,
        )
        return False
    return target > 0 and elapsed >= target


def _atlas_should_emit_target_notification(
    sprint_key: str | None, emitted_key: str | None
) -> bool:
    return bool(sprint_key and sprint_key != emitted_key)


def _atlas_clean_work_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    cleaned = str(summary).strip()
    return cleaned if cleaned else None


def _atlas_timer_owner_id(meta) -> int | None:
    if not isinstance(meta, dict):
        return None
    owner_id = meta.get("timer_owner_id", meta.get("owner_id"))
    if owner_id is None:
        return None
    try:
        return int(owner_id)
    except Exception as exc:
        logger.debug("Invalid timer owner id '%s': %s", owner_id, exc)
        return None


def _atlas_parse_ai_analysis(raw_analysis):
    if not raw_analysis:
        return None
    if isinstance(raw_analysis, dict):
        return raw_analysis
    if isinstance(raw_analysis, str):
        try:
            parsed = json.loads(raw_analysis)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.debug("Failed JSON parse for gemini_analysis payload: %s", exc)
            try:
                parsed = ast.literal_eval(raw_analysis)
                return parsed if isinstance(parsed, dict) else None
            except Exception as nested_exc:
                logger.debug(
                    "Failed literal_eval parse for gemini_analysis payload: %s",
                    nested_exc,
                )
                return None
    return None


def _atlas_ai_overall_score(meta):
    node = meta.get("node")
    precomputed = getattr(node, "ai_overall_score", None)
    if precomputed is not None:
        try:
            return max(0, min(100, int(float(precomputed))))
        except Exception as exc:
            logger.debug(
                "Invalid precomputed ai_overall_score '%s': %s",
                precomputed,
                exc,
            )
    analysis = _atlas_parse_ai_analysis(getattr(node, "gemini_analysis", None))
    if not analysis:
        return None
    score_val = analysis.get("overall_score")
    try:
        return max(0, min(100, int(float(score_val))))
    except Exception as exc:
        logger.debug("Failed to parse atlas AI score value '%s': %s", score_val, exc)
        return None


def _atlas_ai_deadline_warnings(meta):
    node = meta.get("node")
    precomputed_state = str(getattr(node, "ai_deadline_state", "") or "").lower()
    if precomputed_state == "overdue":
        return ["Potentially overdue"]
    if precomputed_state == "risk":
        return ["At risk"]
    analysis = _atlas_parse_ai_analysis(getattr(node, "gemini_analysis", None))
    if not analysis:
        return []
    warnings_list = analysis.get("deadline_warnings") or []
    if not isinstance(warnings_list, list):
        return []
    cleaned = [str(item).strip() for item in warnings_list if str(item).strip()]
    return cleaned


def _is_weighted_mode(value) -> bool:
    mode = str(getattr(value, "value", value) or "").strip().upper()
    return mode == "WEIGHTED"


def _atlas_health_state(meta, index=None, _visited_refs=None, _memo=None):
    """
    Canonical Atlas health engine for map/inspector status surfaces.

    Returns:
      {
        "kind": "done|overdue|risk|inherited|low_progress|on_track",
        "reason": "Complete|Needs care|On track",
        "status_label": <human label>,
        "source": "ai_deadline_warning|ai_overall_score|deadline_status|task_status|inherited_rollup|progress|status_label",
        "needs_attention": bool,
      }
    """
    meta_ref = meta.get("ref")
    if _memo is not None and meta_ref and meta_ref in _memo:
        return _memo[meta_ref]

    progress = int(meta.get("progress", 0) or 0)
    node_type = meta.get("type")
    node = meta.get("node")
    state = getattr(node, "state", LifecycleState.ACTIVE)

    status_label = None
    source = "progress"

    if state != LifecycleState.ACTIVE:
        icon = STATE_ICONS.get(state, "")
        status_label = f"{icon} {state.value.title()}" if icon else state.value.title()
        source = "status_label"
        kind = "inherited"
        if state == LifecycleState.GRADING:
            kind = "risk"
        elif state == LifecycleState.ARCHIVED:
            kind = "on_track"

        return {
            "kind": kind,
            "reason": status_label,
            "status_label": status_label,
            "source": source,
            "needs_attention": state == LifecycleState.GRADING,
        }

    if node_type == "TASK":
        task_status = str(
            getattr(getattr(node, "status", None), "value", getattr(node, "status", ""))
        ).lower()
        if task_status == "done":
            status_label = "Done"
            source = "task_status"
        elif task_status == "in_progress" and progress <= 0:
            status_label = "In progress"
            source = "task_status"
        else:
            deadline = getattr(node, "deadline", None)
            if deadline is not None:
                try:
                    from src.utils.deadline_utils import get_deadline_status

                    _, status_label, _ = get_deadline_status(node)
                    source = "deadline_status"
                except Exception as exc:
                    logger.debug(
                        "Failed to compute deadline health for node '%s': %s",
                        getattr(node, "id", None),
                        exc,
                    )
                    status_label = None
            if not status_label:
                if progress >= 100:
                    status_label = "Done"
                elif progress <= 0:
                    status_label = "Not started"
                else:
                    status_label = "In progress"

    elif node_type == "KEY_RESULT":
        ai_warnings = [str(w).lower() for w in _atlas_ai_deadline_warnings(meta)]
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
    elif node_type == "OBJECTIVE":
        if hasattr(node, "key_results") and node.key_results:
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
            weighted = _is_weighted_mode(getattr(node, "score_mode", None))
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

    if status_label is None:
        if progress >= 100:
            status_label = "Done"
        elif progress < 40:
            status_label = "Needs attention"
        else:
            status_label = "In progress"

    if progress >= 100:
        kind = "done"
    else:
        status_lower = str(status_label).lower()
        if "done" in status_lower or "complete" in status_lower:
            kind = "done"
            if source == "progress":
                source = "status_label"
        elif "overdue" in status_lower:
            kind = "overdue"
            if source == "progress":
                source = "status_label"
        elif "risk" in status_lower:
            kind = "risk"
            if source == "progress":
                source = "status_label"
        else:
            kind = None

    if kind is None and index is not None:
        visited_refs = set(_visited_refs or [])
        meta_ref = meta.get("ref")
        if meta_ref:
            visited_refs.add(meta_ref)
        child_refs = list(meta.get("children") or [])
        for child_ref in child_refs:
            if child_ref in visited_refs:
                continue
            child_meta = index.get(child_ref)
            if not child_meta:
                continue
            child_health = _atlas_health_state(
                child_meta,
                index=index,
                _visited_refs=visited_refs,
                _memo=_memo,
            )
            if child_health.get("needs_attention"):
                kind = "inherited"
                source = "inherited_rollup"
                break

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


def _atlas_health_index(index):
    if not isinstance(index, dict) or not index:
        return {}
    memo = {}
    health_by_ref = {}
    for ref, meta in index.items():
        if not isinstance(meta, dict):
            continue
        health_by_ref[ref] = _atlas_health_state(meta, index=index, _memo=memo)
    return health_by_ref


def _atlas_health_fill_color(health, progress: int, meta=None) -> str:
    kind = str((health or {}).get("kind") or "")

    if meta and meta.get("type") in ["GOAL", "OBJECTIVE", "KEY_RESULT"]:
        node = meta.get("node")
        if meta.get("type") == "KEY_RESULT":
            score = calculate_kr_score(
                getattr(node, "current_value", 0.0),
                getattr(node, "target_value", 100.0),
                getattr(node, "start_value", 0.0),
                getattr(node, "metric_type", "NUMERIC"),
            )
        elif meta.get("type") == "OBJECTIVE":
            score = 0.0
            krs = getattr(node, "key_results", [])
            if krs:
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
                weighted = _is_weighted_mode(getattr(node, "score_mode", None))
                score = calculate_objective_score(
                    kr_scores,
                    kr_weights if weighted else None,
                    weighted=weighted,
                )
        else:
            score = 0.0
            objectives = getattr(node, "objectives", [])
            obj_scores = []
            for obj in objectives:
                krs = getattr(obj, "key_results", [])
                if krs:
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
                    weighted = _is_weighted_mode(getattr(obj, "score_mode", None))
                    obj_scores.append(
                        calculate_objective_score(
                            kr_scores,
                            kr_weights if weighted else None,
                            weighted=weighted,
                        )
                    )
            if obj_scores:
                score = sum(obj_scores) / len(obj_scores)

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


def _atlas_health_source_explanation(source: str | None) -> str:
    source_key = str(source or "").strip().lower()
    mapping = {
        "ai_deadline_warning": "AI detected deadline risk signals.",
        "ai_overall_score": "AI overall score drove this assessment.",
        "deadline_status": "Task deadline timing drove this assessment.",
        "task_status": "Task workflow status drove this assessment.",
        "inherited_rollup": "Inherited from child items that need care.",
        "progress": "Progress threshold rules drove this assessment.",
        "status_label": "Status label rules drove this assessment.",
    }
    return mapping.get(source_key, "Health rules drove this assessment.")


def _atlas_status_label(meta, index=None):
    return _atlas_health_state(meta, index=index).get("status_label", "In progress")


def _atlas_attention_kind(meta, index=None) -> str:
    return str(_atlas_health_state(meta, index=index).get("kind") or "on_track")


def _atlas_needs_attention(meta, index=None) -> bool:
    return bool(_atlas_health_state(meta, index=index).get("needs_attention"))


def _atlas_attention_reason(meta, index=None) -> str:
    return str(_atlas_health_state(meta, index=index).get("reason") or "On track")


def _atlas_point_value(point, keys):
    return atlas_selection_event_helpers.atlas_point_value(point, keys)


def _atlas_extract_clicked_ref(
    selected_point, point_refs=None, label_lookup=None
) -> str | None:
    return atlas_selection_event_helpers.atlas_extract_clicked_ref(
        selected_point,
        point_refs=point_refs,
        label_lookup=label_lookup,
    )


def _atlas_extract_clicked_ref_from_points(
    points,
    index=None,
    current_selected: str | None = None,
    point_refs=None,
    label_lookup=None,
) -> str | None:
    return atlas_selection_event_helpers.atlas_extract_clicked_ref_from_points(
        points,
        index=index,
        current_selected=current_selected,
        point_refs=point_refs,
        label_lookup=label_lookup,
    )


def _atlas_extract_selection_points(event_payload):
    return atlas_selection_event_helpers.atlas_extract_selection_points(event_payload)


def _atlas_task_rollup(task_refs, index, health_index=None):
    rollup = {
        "total": 0,
        "running": 0,
        "attention": 0,
        "done": 0,
    }
    if health_index is None:
        health_index = _atlas_health_index(index)

    for ref in task_refs:
        meta = index.get(ref)
        if not meta or meta.get("type") != "TASK":
            continue
        rollup["total"] += 1

        task = meta.get("node")
        if getattr(task, "timer_started_at", None) is not None:
            rollup["running"] += 1

        progress = int(meta.get("progress", 0) or 0)
        if progress >= 100:
            rollup["done"] += 1
        health = health_index.get(ref)
        if health is None:
            health = _atlas_health_state(meta, index=index)
        if bool(health.get("needs_attention")):
            rollup["attention"] += 1

    return rollup


def _atlas_health_debug_rows(refs, index, health_index=None, limit: int = 80):
    rows = []
    kind_rank = {
        "overdue": 0,
        "risk": 1,
        "low_progress": 2,
        "inherited": 2,
        "on_track": 3,
        "done": 4,
    }
    resolved_health = health_index or {}

    for ref in refs:
        meta = index.get(ref)
        if not meta:
            continue
        health = resolved_health.get(ref)
        if health is None:
            health = _atlas_health_state(meta, index=index)
        kind = str(health.get("kind") or "on_track")
        rows.append(
            {
                "Ref": str(ref),
                "Type": str(meta.get("type") or ""),
                "Title": str(meta.get("title") or "Untitled"),
                "Kind": kind,
                "Reason": str(health.get("reason") or "On track"),
                "Status": str(health.get("status_label") or "In progress"),
                "Source": str(health.get("source") or "progress"),
                "Progress": int(meta.get("progress", 0) or 0),
                "NeedsAttention": bool(health.get("needs_attention")),
                "_rank": int(kind_rank.get(kind, 5)),
            }
        )

    rows.sort(key=lambda item: (item["_rank"], item["Progress"], item["Title"].lower()))
    cleaned = []
    for item in rows[: max(1, int(limit or 80))]:
        clean_item = dict(item)
        clean_item.pop("_rank", None)
        cleaned.append(clean_item)
    return cleaned


def _atlas_descendant_refs(root_ref: str, index, limit: int = 350):
    refs = []
    pending = [root_ref]
    seen = set()
    while pending and len(refs) < limit:
        node_ref = pending.pop()
        if node_ref in seen:
            continue
        seen.add(node_ref)
        refs.append(node_ref)
        meta = index.get(node_ref)
        if not meta:
            continue
        for child_ref in reversed(meta.get("children", [])):
            pending.append(child_ref)
    return refs


def _atlas_scope_refs(roots, index, limit: int = 800):
    refs = []
    seen = set()
    for root_ref in roots:
        for ref in _atlas_descendant_refs(root_ref, index, limit=limit):
            if ref in seen:
                continue
            seen.add(ref)
            refs.append(ref)
            if len(refs) >= limit:
                return refs
    return refs
