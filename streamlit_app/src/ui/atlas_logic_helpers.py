"""Shared Atlas policy/parsing helpers used across UI modules."""

from __future__ import annotations

import ast
import json
import logging


logger = logging.getLogger(__name__)


def atlas_ai_progress_decision(
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


def atlas_commit_target_minutes(
    preset_choice: str,
    custom_minutes: int | None = None,
) -> int:
    preset = str(preset_choice or "25m")
    if preset == "50m":
        return 50
    if preset == "Custom":
        if custom_minutes is None:
            return 35
        return max(5, min(240, int(custom_minutes)))
    return 25


def atlas_sprint_run_key(
    task_ref: str | None,
    target_minutes: int,
    started_at_epoch,
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


def atlas_should_show_soft_reminder(
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


def atlas_should_emit_target_notification(
    sprint_key: str | None,
    emitted_key: str | None,
) -> bool:
    return bool(sprint_key and sprint_key != emitted_key)


def atlas_clean_work_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    cleaned = str(summary).strip()
    return cleaned if cleaned else None


def atlas_timer_owner_id(meta) -> int | None:
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


def atlas_parse_ai_analysis(raw_analysis):
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


def atlas_ai_overall_score(meta):
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
    analysis = atlas_parse_ai_analysis(getattr(node, "gemini_analysis", None))
    if not analysis:
        return None
    score_val = analysis.get("overall_score")
    try:
        return max(0, min(100, int(float(score_val))))
    except Exception as exc:
        logger.debug("Failed to parse atlas AI score value '%s': %s", score_val, exc)
        return None


def atlas_ai_deadline_warnings(meta):
    node = meta.get("node")
    precomputed_state = str(getattr(node, "ai_deadline_state", "") or "").lower()
    if precomputed_state == "overdue":
        return ["Potentially overdue"]
    if precomputed_state == "risk":
        return ["At risk"]
    analysis = atlas_parse_ai_analysis(getattr(node, "gemini_analysis", None))
    if not analysis:
        return []
    warnings_list = analysis.get("deadline_warnings") or []
    if not isinstance(warnings_list, list):
        return []
    cleaned = [str(item).strip() for item in warnings_list if str(item).strip()]
    return cleaned


def atlas_is_weighted_mode(value) -> bool:
    mode = str(getattr(value, "value", value) or "").strip().upper()
    return mode == "WEIGHTED"
