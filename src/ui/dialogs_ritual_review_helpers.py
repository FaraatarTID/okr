"""Weekly ritual review-step helpers.

This module extracts the heavy "Step 1: Review Week" flow from
`src.ui.dialogs_ritual_helpers` to keep orchestration compact.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from src.crud import (
    close_experiment,
    create_retrospective,
    list_experiments_for_retro_window,
    upsert_retro_experiment_outcome,
)
from src.models import ExperimentDecision, ExperimentStatus
from src.ui.components import format_time
from src.utils.time_utils import utc_now_naive


def _collect_week_logs(
    username: str, *, cached_get_user_by_username_fn, cached_get_work_logs_by_range_fn
):
    end_date = utc_now_naive()
    start_date = end_date - timedelta(days=7)

    total_minutes = 0
    work_logs_text = []

    logs = []
    current_user_obj = cached_get_user_by_username_fn(username)
    if current_user_obj:
        logs = cached_get_work_logs_by_range_fn(
            current_user_obj.id, start_date, end_date
        )

    for work_log in logs:
        mins = work_log.duration_minutes or 0
        total_minutes += mins

        node_title = None
        try:
            if work_log.task and getattr(work_log.task, "title", None):
                node_title = work_log.task.title
            elif (
                work_log.task
                and work_log.task.key_result
                and getattr(work_log.task.key_result, "title", None)
            ):
                node_title = work_log.task.key_result.title
        except (AttributeError, TypeError):
            node_title = None

        node_title = node_title or "Work"
        summary = (
            getattr(work_log, "summary", None)
            or getattr(work_log, "note", None)
            or "Work"
        )
        work_logs_text.append(f"- {node_title}: {summary} ({int(mins)}m)")

    return start_date, end_date, total_minutes, work_logs_text, current_user_obj


def _render_weekly_ai_summary(
    *,
    username: str,
    start_date,
    end_date,
    total_minutes: int,
    work_logs_text: list[str],
) -> None:
    if "ritual_summary" not in st.session_state:
        if st.button("✨ Generate AI Summary", type="primary"):
            with st.spinner("Analyzing your week..."):
                from src.services.ai_service import generate_weekly_summary

                stats = {
                    "total_minutes": total_minutes,
                    "tasks_completed": 0,
                    "krs_updated": 0,
                    "work_logs_text": "\n".join(work_logs_text[:50]),
                }
                res = generate_weekly_summary(
                    username,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    stats,
                )
                if "error" not in res:
                    st.session_state.ritual_summary = res
                    st.rerun()
                else:
                    st.error(res["error"])

    summary = st.session_state.get("ritual_summary")
    if summary:
        st.markdown(summary.get("summary_markdown"))
        for highlight in summary.get("highlights", []):
            st.success(highlight)
        st.info(f"💡 **Focus Analysis:** {summary.get('focus_analysis')}")


def _find_existing_week_retro(
    current_user_obj, cycle_id: int, start_date, *, cached_get_user_retrospectives_fn
):
    existing_retro = None
    if current_user_obj:
        past_retros = cached_get_user_retrospectives_fn(current_user_obj.id, cycle_id)
        for retro in past_retros:
            if retro.week_start_date.date() == start_date.date():
                existing_retro = retro
                break
    return existing_retro


def _load_review_experiments(*, cycle_id: int, start_date, username: str):
    window_end = start_date + timedelta(days=7)
    exp_review_key = f"retro_exps_{cycle_id}_{start_date.isoformat()}"
    if exp_review_key not in st.session_state:
        try:
            st.session_state[exp_review_key] = list_experiments_for_retro_window(
                cycle_id=cycle_id,
                window_start=start_date,
                window_end=window_end,
                actor_username=username,
            )
        except PermissionError:
            st.session_state[exp_review_key] = []
    return st.session_state.get(exp_review_key, [])


def _render_review_experiments(review_experiments) -> None:
    if review_experiments:
        for exp in review_experiments:
            status_bad = {"PLANNED": "⚪", "RUNNING": "🟢", "DECIDED": "🔵"}.get(
                exp.status.value,
                "⚪",
            )
            with st.container(border=True):
                st.markdown(
                    f"**{status_bad} {exp.hypothesis[:60]}{'...' if len(exp.hypothesis) > 60 else ''}**"
                )
                st.caption(
                    f"Status: {exp.status.value} | Created: {exp.created_at.strftime('%Y-%m-%d')}"
                )

                dec_key = f"retro_dec_{exp.id}"
                rat_key = f"retro_rat_{exp.id}"
                c_dec, c_rat = st.columns([1, 2])
                with c_dec:
                    st.selectbox(
                        "Decision",
                        options=["", "ADOPT", "REVERT", "ITERATE", "UNKNOWN"],
                        key=dec_key,
                        label_visibility="collapsed",
                    )
                with c_rat:
                    st.text_input(
                        "Rationale (optional)",
                        key=rat_key,
                        label_visibility="collapsed",
                        placeholder="Why this decision?",
                    )
    else:
        st.info("No experiments to review this week.")


def _save_retro_and_outcomes(
    *,
    retro_input: str,
    current_user_obj,
    cycle_id: int,
    start_date,
    review_experiments,
    username: str,
):
    saved_retro = None
    if retro_input and current_user_obj:
        saved_retro = create_retrospective(
            user_id=current_user_obj.id,
            cycle_id=cycle_id,
            week_start_date=start_date,
            content=retro_input,
            actor_username=username,
        )
        st.toast("Retrospective Saved!")

    if saved_retro and review_experiments:
        for exp in review_experiments:
            dec_key = f"retro_dec_{exp.id}"
            rat_key = f"retro_rat_{exp.id}"
            decision_val = st.session_state.get(dec_key, "")
            rationale_val = st.session_state.get(rat_key, "")

            if decision_val:
                try:
                    dec_enum = ExperimentDecision(decision_val)
                    upsert_retro_experiment_outcome(
                        retrospective_id=saved_retro.id,
                        experiment_id=exp.id,
                        decision=dec_enum,
                        rationale=rationale_val if rationale_val else None,
                        actor_username=username,
                    )
                    if exp.status != ExperimentStatus.DECIDED:
                        close_experiment(
                            experiment_id=exp.id,
                            decision=dec_enum,
                            rationale=rationale_val if rationale_val else "",
                            actor_username=username,
                        )
                except Exception as exc:
                    st.warning(f"Could not save outcome for experiment {exp.id}: {exc}")


def render_review_week_step_content(
    username: str,
    cycle_id: int,
    *,
    cached_get_user_by_username_fn,
    cached_get_work_logs_by_range_fn,
    cached_get_user_retrospectives_fn,
) -> None:
    """Render step 1 of weekly ritual: review, retrospective, experiment outcomes."""
    st.markdown("#### 📅 Week in Review")

    start_date, end_date, total_minutes, work_logs_text, current_user_obj = (
        _collect_week_logs(
            username,
            cached_get_user_by_username_fn=cached_get_user_by_username_fn,
            cached_get_work_logs_by_range_fn=cached_get_work_logs_by_range_fn,
        )
    )
    _render_weekly_ai_summary(
        username=username,
        start_date=start_date,
        end_date=end_date,
        total_minutes=total_minutes,
        work_logs_text=work_logs_text,
    )
    st.markdown(f"**Total Focus Time:** {format_time(total_minutes)} this week.")

    st.markdown("---")
    st.markdown("#### 📝 Your Retrospective")
    st.caption(
        "Reflect on your week. What went well? What blocked you? This is visible to your manager."
    )

    existing_retro = _find_existing_week_retro(
        current_user_obj,
        cycle_id,
        start_date,
        cached_get_user_retrospectives_fn=cached_get_user_retrospectives_fn,
    )
    default_retro = existing_retro.content if existing_retro else ""
    retro_input = st.text_area(
        "Your Thoughts",
        value=default_retro,
        height=150,
        key="retro_input_area",
    )

    st.markdown("---")
    st.markdown("#### 🔬 Experiments Reviewed This Week")
    st.caption("Record decisions for experiments that concluded or are still running.")
    review_experiments = _load_review_experiments(
        cycle_id=cycle_id,
        start_date=start_date,
        username=username,
    )
    _render_review_experiments(review_experiments)

    col_r1, _ = st.columns([1, 4])
    if col_r1.button("Next: Update KRs ➡️", type="primary"):
        _save_retro_and_outcomes(
            retro_input=retro_input,
            current_user_obj=current_user_obj,
            cycle_id=cycle_id,
            start_date=start_date,
            review_experiments=review_experiments,
            username=username,
        )
        st.session_state.ritual_step = 2
        st.rerun()
