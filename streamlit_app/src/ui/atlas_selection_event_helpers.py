"""Selection/click extraction helpers for Atlas point payloads."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


def atlas_point_value(point: Any, keys) -> Any:
    key_candidates = keys if isinstance(keys, (list, tuple)) else [keys]
    for key in key_candidates:
        if isinstance(point, dict):
            if key in point:
                return point.get(key)
        else:
            value = getattr(point, key, None)
            if value is not None:
                return value
    return None


def atlas_extract_clicked_ref(
    selected_point,
    point_refs=None,
    label_lookup=None,
) -> str | None:
    if selected_point is None:
        return None

    clicked_ref = None
    customdata = atlas_point_value(selected_point, "customdata")
    if isinstance(customdata, (list, tuple)) and customdata:
        clicked_ref = customdata[0]
        if isinstance(clicked_ref, (list, tuple)) and clicked_ref:
            clicked_ref = clicked_ref[0]
    elif isinstance(customdata, str):
        clicked_ref = customdata
    elif isinstance(customdata, dict):
        clicked_ref = customdata.get("ref") or customdata.get("id")

    if not clicked_ref:
        clicked_ref = atlas_point_value(selected_point, "id")

    if not clicked_ref and point_refs:
        raw_idx = atlas_point_value(
            selected_point,
            ("point_index", "pointIndex", "point_number", "pointNumber"),
        )
        if raw_idx is not None:
            try:
                point_idx = int(raw_idx)
            except Exception as exc:
                logger.debug("Invalid treemap point index '%s': %s", raw_idx, exc)
                point_idx = -1
            if 0 <= point_idx < len(point_refs):
                clicked_ref = point_refs[point_idx]

    if not clicked_ref and label_lookup:
        point_label = atlas_point_value(selected_point, ("label", "text"))
        if point_label is not None:
            matched_refs = label_lookup.get(str(point_label), [])
            if len(matched_refs) == 1:
                clicked_ref = matched_refs[0]

    if clicked_ref is None:
        return None
    return str(clicked_ref)


def atlas_extract_clicked_ref_from_points(
    points,
    index=None,
    current_selected: str | None = None,
    point_refs=None,
    label_lookup=None,
) -> str | None:
    if not points:
        return None

    refs = []
    for point in points:
        ref = atlas_extract_clicked_ref(
            point,
            point_refs=point_refs,
            label_lookup=label_lookup,
        )
        if ref:
            refs.append(ref)
    if not refs:
        return None

    unique_refs = []
    for ref in refs:
        if ref not in unique_refs:
            unique_refs.append(ref)

    if current_selected and current_selected in unique_refs and len(unique_refs) > 1:
        candidate_refs = [ref for ref in unique_refs if ref != current_selected]
    else:
        candidate_refs = list(unique_refs)

    if index is not None:
        in_index = [ref for ref in candidate_refs if ref in index]
        if in_index:
            candidate_refs = in_index
        else:
            return None
        return max(
            candidate_refs,
            key=lambda ref: int(index.get(ref, {}).get("depth", -1)),
        )

    return candidate_refs[-1]


def atlas_extract_selection_points(event_payload):
    if event_payload is None:
        return []

    if isinstance(event_payload, list):
        return list(event_payload)

    if isinstance(event_payload, dict):
        selection_data = event_payload.get("selection")
    else:
        selection_data = getattr(event_payload, "selection", None)

    if selection_data is None:
        return []
    if isinstance(selection_data, dict):
        points = selection_data.get("points", [])
    else:
        points = getattr(selection_data, "points", [])
    return list(points or [])
