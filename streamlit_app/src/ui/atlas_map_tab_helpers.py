"""Atlas focus map tab orchestration helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import atlas_focus_map_shell_helpers
from src.ui import atlas_map_chart_helpers
from src.ui import atlas_map_sidebar_helpers
from src.ui import atlas_workspace_helpers


def render_focus_map_tab_content(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    username: str,
    selected_meta: dict[str, Any],
    node_lookup: dict[str, Any],
    type_icons: dict[str, str],
    get_node_details_fn: Callable[..., dict[str, Any]],
    escape_html_fn: Callable[[str], str],
    is_mobile_request: bool,
    child_type_map: dict[str, str],
    selected_ref: str,
    roots: list[str],
    index: dict[str, Any],
    scope_refs_fn: Callable[..., list[str]],
    descendant_refs_fn: Callable[..., list[str]],
    role_value: str,
    health_index: dict[str, Any] | None,
    health_debug_rows_fn: Callable[..., list[dict[str, Any]]],
    actor_id: int | None,
    selected_scope: str,
    focus_task_ref: str | None,
    selected_path_refs: list[str],
    runtime_token: str,
    cached_treemap_fn: Callable[..., Any],
    plotly_events_fn: Callable[..., list[Any] | None] | None,
    extract_selection_points_fn: Callable[[Any], list[dict[str, Any]]],
    extract_clicked_ref_from_points_fn: Callable[..., str | None],
    health_state_fn: Callable[..., dict[str, Any]],
    ai_progress_decision_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[..., float],
    next_score_fn: Callable[..., float],
    from_epoch_millis_fn: Callable[[Any], Any],
    from_epoch_seconds_fn: Callable[[Any], Any],
    logger: Any,
    rerun_fn: Callable[[], Any],
) -> None:
    with st_module.container(border=True):
        map_chart_area, map_sidebar_area = (
            atlas_focus_map_shell_helpers.render_focus_map_shell(
                st_module=st_module,
                selected_meta=selected_meta,
                node_lookup=node_lookup,
                type_icons=type_icons,
                get_node_details_fn=get_node_details_fn,
                escape_html_fn=escape_html_fn,
                is_mobile_request=is_mobile_request,
            )
        )

        child_type = child_type_map.get(selected_meta["type"])
        atlas_map_sidebar_helpers.render_map_key_and_create_actions(
            sidebar=map_sidebar_area,
            session_state=session_state,
            selected_ref=selected_ref,
            child_type=child_type,
            rerun_fn=rerun_fn,
        )
        map_lens, map_refs, map_kr_refs, map_task_refs = (
            atlas_map_sidebar_helpers.resolve_map_lens_and_refs(
                sidebar=map_sidebar_area,
                session_state=session_state,
                roots=roots,
                index=index,
                selected_ref=selected_ref,
                scope_refs_fn=scope_refs_fn,
                descendant_refs_fn=descendant_refs_fn,
            )
        )
        atlas_map_sidebar_helpers.render_health_debug_panel(
            sidebar=map_sidebar_area,
            session_state=session_state,
            role_value=role_value,
            map_refs=map_refs,
            index=index,
            health_index=health_index,
            health_debug_rows_fn=health_debug_rows_fn,
        )
        (
            apply_ai_score_to_progress,
            preview_ai_sync,
            max_progress_delta,
            allow_progress_decrease,
        ) = atlas_map_sidebar_helpers.render_ai_control_panel(
            sidebar=map_sidebar_area,
            session_state=session_state,
            has_kr_refs=bool(map_kr_refs),
        )

        from src.crud import (
            recalculate_rollup_for_key_results,
            update_key_result,
        )

        atlas_map_sidebar_helpers.handle_ai_progress_undo_action(
            sidebar=map_sidebar_area,
            session_state=session_state,
            username=username,
            apply_ai_progress_undo_fn=atlas_workspace_helpers.apply_ai_progress_undo,
            update_key_result_fn=update_key_result,
            recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results,
            rerun_fn=rerun_fn,
        )

        from src.services.ai_service import (
            analyze_node,
            suggest_critical_task,
        )

        atlas_map_sidebar_helpers.handle_ai_progress_sync_action(
            sidebar=map_sidebar_area,
            session_state=session_state,
            map_kr_refs=map_kr_refs,
            map_task_refs=map_task_refs,
            index=index,
            health_index=health_index,
            actor_id=actor_id,
            selected_scope=selected_scope,
            map_lens=map_lens,
            selected_node_title=str(selected_meta.get("title") or ""),
            username=username,
            apply_ai_score_to_progress=apply_ai_score_to_progress,
            preview_ai_sync=preview_ai_sync,
            max_progress_delta=max_progress_delta,
            allow_progress_decrease=allow_progress_decrease,
            run_ai_progress_sync_fn=atlas_workspace_helpers.run_ai_progress_sync,
            analyze_node_fn=analyze_node,
            suggest_critical_task_fn=suggest_critical_task,
            update_key_result_fn=update_key_result,
            recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results,
            ai_progress_decision_fn=ai_progress_decision_fn,
            health_state_fn=health_state_fn,
            ai_overall_score_fn=ai_overall_score_fn,
            next_score_fn=next_score_fn,
            deadline_to_iso_fn=lambda deadline_raw: (
                atlas_workspace_helpers.deadline_to_iso(
                    deadline_raw,
                    from_epoch_millis_fn=from_epoch_millis_fn,
                    from_epoch_seconds_fn=from_epoch_seconds_fn,
                    logger=logger,
                )
            ),
            logger=logger,
            rerun_fn=rerun_fn,
        )

        atlas_map_sidebar_helpers.render_ai_sync_report_feedback(
            sidebar=map_sidebar_area,
            session_state=session_state,
            index=index,
            build_ai_sync_sidebar_messages_fn=(
                atlas_workspace_helpers.build_ai_sync_sidebar_messages
            ),
            dataframe_fn=st_module.dataframe,
        )
        atlas_map_sidebar_helpers.render_ai_undo_report_feedback(
            sidebar=map_sidebar_area,
            session_state=session_state,
            build_ai_undo_sidebar_messages_fn=(
                atlas_workspace_helpers.build_ai_undo_sidebar_messages
            ),
        )

        atlas_map_chart_helpers.render_map_chart_and_handle_navigation(
            map_chart_area=map_chart_area,
            session_state=session_state,
            map_refs=map_refs,
            index=index,
            selected_ref=selected_ref,
            focus_task_ref=focus_task_ref,
            selected_path_refs=selected_path_refs,
            health_index=health_index,
            runtime_token=runtime_token,
            is_mobile_request=is_mobile_request,
            cached_treemap_fn=cached_treemap_fn,
            plotly_events_fn=plotly_events_fn,
            extract_selection_points_fn=extract_selection_points_fn,
            extract_clicked_ref_from_points_fn=extract_clicked_ref_from_points_fn,
            collect_task_refs_fn=atlas_workspace_helpers.collect_task_refs,
            suggest_focus_task_fn=atlas_workspace_helpers.suggest_focus_task,
            health_state_fn=health_state_fn,
            rerun_fn=rerun_fn,
            logger=logger,
        )
        atlas_map_chart_helpers.render_no_tasks_message(
            sidebar=map_sidebar_area,
            map_task_refs=map_task_refs,
            map_lens=map_lens,
        )
