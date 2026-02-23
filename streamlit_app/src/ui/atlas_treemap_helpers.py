"""Atlas treemap/render support helpers extracted from components."""

from __future__ import annotations

import json
import logging
from typing import Callable

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from src.domain.scoring import (
    calculate_kr_score,
    calculate_objective_score,
    get_score_label,
)
from src.ui.atlas_helpers import (
    _atlas_health_fill_color,
    _atlas_health_source_explanation,
    _atlas_health_state,
)
from src.ui.styles import TYPE_ICONS


logger = logging.getLogger(__name__)

ATLAS_TREEMAP_CACHE_STATE_KEY = "_atlas_treemap_figure_cache"
ATLAS_TREEMAP_CACHE_ORDER_KEY = "_atlas_treemap_figure_cache_order"
ATLAS_TREEMAP_CACHE_MAX_ENTRIES = 8


def atlas_fire_browser_notification(title: str, body: str) -> None:
    title_json = json.dumps(str(title or "Sprint update"))
    body_json = json.dumps(str(body or "Target reached"))
    components.html(
        f"""
        <script>
        (function () {{
          const title = {title_json};
          const body = {body_json};
          try {{
            const beep = () => {{
              const Ctx = window.AudioContext || window.webkitAudioContext;
              if (!Ctx) return;
              const ctx = new Ctx();
              const osc = ctx.createOscillator();
              const gain = ctx.createGain();
              osc.type = "sine";
              osc.frequency.value = 880;
              gain.gain.value = 0.04;
              osc.connect(gain);
              gain.connect(ctx.destination);
              osc.start();
              setTimeout(() => {{
                osc.stop();
                if (ctx.close) ctx.close();
              }}, 180);
            }};
            beep();
            if (!("Notification" in window)) return;
            if (Notification.permission === "granted") {{
              new Notification(title, {{ body }});
              return;
            }}
            if (Notification.permission === "default") {{
              Notification.requestPermission().then((permission) => {{
                if (permission === "granted") {{
                  new Notification(title, {{ body }});
                }}
              }});
            }}
          }} catch (e) {{
            // best-effort only
          }}
        }})();
        </script>
        """,
        height=0,
    )


def atlas_is_mobile_request() -> bool:
    """Best-effort mobile detection from Streamlit request headers."""
    user_agent = ""
    try:
        context_obj = getattr(st, "context", None)
        header_map = getattr(context_obj, "headers", None)
        if header_map:
            user_agent = str(
                header_map.get("user-agent") or header_map.get("User-Agent") or ""
            ).lower()
    except Exception as exc:
        logger.debug("Failed to read request headers for mobile detection: %s", exc)
        user_agent = ""

    if not user_agent:
        return False

    mobile_tokens = (
        "android",
        "iphone",
        "ipad",
        "ipod",
        "mobile",
        "windows phone",
    )
    return any(token in user_agent for token in mobile_tokens)


def atlas_treemap_cache_key(
    runtime_token,
    refs,
    selected_ref,
    focus_task_ref,
    selected_path_refs,
    chart_height: int,
):
    refs_key = tuple(str(ref) for ref in (refs or []))
    path_key = tuple(sorted(str(ref) for ref in (selected_path_refs or [])))
    return (
        str(runtime_token or ""),
        refs_key,
        str(selected_ref or ""),
        str(focus_task_ref or ""),
        path_key,
        int(chart_height),
    )


def _is_weighted_mode(value) -> bool:
    mode = str(getattr(value, "value", value) or "").strip().upper()
    return mode == "WEIGHTED"


def build_atlas_treemap(
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
):
    ids = []
    labels = []
    parents = []
    values = []
    fill_colors = []
    line_colors = []
    line_widths = []
    custom = []
    local_health_memo = {}

    path_refs = set(selected_path_refs or [])

    for ref in refs:
        meta = index.get(ref)
        if not meta:
            continue
        title = meta.get("title") or "Untitled"
        if len(title) > 36:
            title = f"{title[:33]}..."
        parent_ref = meta.get("parent") if meta.get("parent") in refs else ""
        progress = int(meta.get("progress", 0) or 0)
        node_type = meta.get("type")
        health = (
            (health_index or {}).get(ref) if isinstance(health_index, dict) else None
        )
        if health is None:
            health = _atlas_health_state(meta, index=index, _memo=local_health_memo)

        status = str(health.get("status_label") or "In progress")

        if node_type in ["KEY_RESULT", "OBJECTIVE"]:
            node_obj = meta.get("node")
            if node_type == "KEY_RESULT":
                score = calculate_kr_score(
                    getattr(node_obj, "current_value", 0.0),
                    getattr(node_obj, "target_value", 100.0),
                    getattr(node_obj, "start_value", 0.0),
                    getattr(node_obj, "metric_type", "NUMERIC"),
                )
            else:
                obj_score = 0.0
                krs = getattr(node_obj, "key_results", [])
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
                    weighted = _is_weighted_mode(getattr(node_obj, "score_mode", None))
                    obj_score = calculate_objective_score(
                        kr_scores,
                        kr_weights if weighted else None,
                        weighted=weighted,
                    )
                score = obj_score

            score_label = get_score_label(score)
            status = f"Score: {score:.2f} ({score_label})"
            attention_reason = score_label
        else:
            attention_reason = str(health.get("reason") or "On track")
        source_explanation = _atlas_health_source_explanation(health.get("source"))

        child_count = len(meta.get("children", []))
        value = 10 if child_count <= 0 else 0

        fill = _atlas_health_fill_color(health, progress, meta=meta)

        line_color = "#f5ede0"
        line_width = 1.4
        if ref in path_refs:
            line_color = "#b9914a"
            line_width = 2.0
        if ref == selected_ref:
            line_color = "#8a6827"
            line_width = 3.2
        if ref == focus_task_ref:
            line_color = "#0d9488"
            line_width = 3.6

        ids.append(ref)
        labels.append(f"{TYPE_ICONS.get(node_type, '')} {title}")
        parents.append(parent_ref)
        values.append(value)
        fill_colors.append(fill)
        line_colors.append(line_color)
        line_widths.append(line_width)
        custom.append(
            [
                ref,
                (
                    f"{node_type.replace('_', ' ').title()} | {status} | {progress}%"
                    f" | {attention_reason}"
                ),
                source_explanation,
            ]
        )

    if not ids:
        return None

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="remainder",
            marker=dict(
                colors=fill_colors,
                line=dict(color=line_colors, width=line_widths),
            ),
            textinfo="label",
            customdata=custom,
            hovertemplate=(
                "<b>%{label}</b><br>%{customdata[1]}"
                "<br>Why: %{customdata[2]}<extra></extra>"
            ),
            sort=False,
            tiling=dict(pad=4, packing="slice-dice"),
            pathbar=dict(visible=False),
        )
    )
    fig.update_layout(
        margin=dict(l=8, r=8, t=10, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13, color="#1f2933"),
        height=int(chart_height),
        clickmode="event+select",
    )
    return fig


def atlas_cached_treemap(
    session_state,
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    *,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
    runtime_token=None,
    build_fn: Callable[..., object | None] | None = None,
    cache_state_key: str = ATLAS_TREEMAP_CACHE_STATE_KEY,
    cache_order_key: str = ATLAS_TREEMAP_CACHE_ORDER_KEY,
    cache_max_entries: int = ATLAS_TREEMAP_CACHE_MAX_ENTRIES,
):
    cache = session_state.get(cache_state_key)
    if not isinstance(cache, dict):
        cache = {}
    order = session_state.get(cache_order_key)
    if not isinstance(order, list):
        order = []

    cache_key = atlas_treemap_cache_key(
        runtime_token,
        refs,
        selected_ref,
        focus_task_ref,
        selected_path_refs,
        chart_height,
    )
    hit = cache.get(cache_key)
    if hit is not None:
        if cache_key in order:
            order.remove(cache_key)
        order.append(cache_key)
        session_state[cache_order_key] = order
        session_state[cache_state_key] = cache
        return hit

    build_fn = build_fn or build_atlas_treemap
    built = build_fn(
        refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=chart_height,
        health_index=health_index,
    )
    if built is None:
        return None

    cache[cache_key] = built
    if cache_key in order:
        order.remove(cache_key)
    order.append(cache_key)
    while len(order) > int(cache_max_entries):
        stale_key = order.pop(0)
        cache.pop(stale_key, None)

    session_state[cache_order_key] = order
    session_state[cache_state_key] = cache
    return built
