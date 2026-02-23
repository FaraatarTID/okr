"""Atlas runtime snapshot/lookup helper utilities."""

from __future__ import annotations

from typing import Any, Callable

from src.ui.session_keys import ATLAS_NODE_LOOKUP


def extract_ai_snapshot_fields(
    raw_analysis: Any,
    *,
    parse_ai_analysis_fn: Callable[[Any], Any],
    logger: Any | None = None,
) -> tuple[int | None, str | None]:
    ai_overall_score = None
    ai_deadline_state = None

    analysis = parse_ai_analysis_fn(raw_analysis)
    if not isinstance(analysis, dict):
        return ai_overall_score, ai_deadline_state

    try:
        score_raw = analysis.get("overall_score")
        if score_raw is not None:
            ai_overall_score = max(0, min(100, int(float(score_raw))))
    except (TypeError, ValueError) as exc:
        if logger is not None:
            logger.debug(
                "Failed to parse atlas AI overall score '%s': %s",
                analysis.get("overall_score"),
                exc,
            )
        ai_overall_score = None

    warnings_list = analysis.get("deadline_warnings") or []
    if isinstance(warnings_list, list) and warnings_list:
        joined = " ".join(
            str(item) for item in warnings_list if item is not None
        ).lower()
        ai_deadline_state = "overdue" if "overdue" in joined else "risk"

    return ai_overall_score, ai_deadline_state


def build_node_lookup(index: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    return {
        str(ref): {
            "type": str(meta.get("type") or ""),
            "title": str(meta.get("title") or "Unknown"),
        }
        for ref, meta in (index or {}).items()
    }


def get_node_details_from_lookup(
    node_id: Any,
    *,
    node_lookup: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    lookup = node_lookup
    if lookup is None and isinstance(session_state, dict):
        candidate = session_state.get(ATLAS_NODE_LOOKUP)
        lookup = candidate if isinstance(candidate, dict) else {}
    if not isinstance(lookup, dict):
        return None, None

    hit = lookup.get(str(node_id))
    if not isinstance(hit, dict):
        return None, None
    node_type = str(hit.get("type") or "").upper() or None
    title = str(hit.get("title") or "Unknown")
    return node_type, title
