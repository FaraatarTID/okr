"""Weekly ritual dialog content helpers.

Extracted from `src.ui.dialogs` to keep the dialog facade compact while
preserving existing UI behavior and state transitions.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from src.crud import (
    close_experiment,
    create_check_in,
    create_experiment,
    create_retrospective,
    create_weekly_plan,
    get_active_experiments_for_kr,
    list_experiments_for_retro_window,
    update_experiment,
    upsert_retro_experiment_outcome,
)
from src.models import (
    ExperimentDecision,
    ExperimentStatus,
    ExpectedEffectDirection,
    VariationType,
)
from src.ui.components import format_time
from src.utils.time_utils import utc_now_naive


def _render_weekly_ritual_chrome() -> None:
    st.markdown(
        """
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### Weekly Check-in Ritual")
    if c_close.button("", icon=":material/close:", key="close_ritual"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        if "ritual_step" in st.session_state:
            del st.session_state.ritual_step
        st.rerun()


def _render_ritual_stepper(step: int) -> None:
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f"**1. Review Week** {'✅' if step > 1 else '🔵' if step == 1 else '⚪'}"
    )
    c2.markdown(
        f"**2. Update KRs** {'✅' if step > 2 else '🔵' if step == 2 else '⚪'}"
    )
    c3.markdown(f"**3. Plan Next** {'✅' if step > 3 else '🔵' if step == 3 else '⚪'}")
    st.markdown("---")


def _render_review_week_step(
    username: str,
    cycle_id: int,
    *,
    cached_get_user_by_username_fn,
    cached_get_work_logs_by_range_fn,
    cached_get_user_retrospectives_fn,
) -> None:
    st.markdown("#### 📅 Week in Review")

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

    for wl in logs:
        mins = wl.duration_minutes or 0
        total_minutes += mins

        node_title = None
        try:
            if wl.task and getattr(wl.task, "title", None):
                node_title = wl.task.title
            elif (
                wl.task
                and wl.task.key_result
                and getattr(wl.task.key_result, "title", None)
            ):
                node_title = wl.task.key_result.title
        except (AttributeError, TypeError):
            node_title = None

        node_title = node_title or "Work"
        summary = getattr(wl, "summary", None) or getattr(wl, "note", None) or "Work"
        work_logs_text.append(f"- {node_title}: {summary} ({int(mins)}m)")

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
        for h in summary.get("highlights", []):
            st.success(h)
        st.info(f"💡 **Focus Analysis:** {summary.get('focus_analysis')}")

    st.markdown(f"**Total Focus Time:** {format_time(total_minutes)} this week.")

    st.markdown("---")
    st.markdown("#### 📝 Your Retrospective")
    st.caption(
        "Reflect on your week. What went well? What blocked you? This is visible to your manager."
    )

    existing_retro = None
    if current_user_obj:
        past_retros = cached_get_user_retrospectives_fn(current_user_obj.id, cycle_id)
        for retro in past_retros:
            if retro.week_start_date.date() == start_date.date():
                existing_retro = retro
                break

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

    review_experiments = st.session_state.get(exp_review_key, [])

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

    col_r1, _ = st.columns([1, 4])
    if col_r1.button("Next: Update KRs ➡️", type="primary"):
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
                        st.warning(
                            f"Could not save outcome for experiment {exp.id}: {exc}"
                        )

        st.session_state.ritual_step = 2
        st.rerun()


def _render_update_krs_step(
    username: str,
    cycle_id: int,
    *,
    cached_get_krs_needing_checkin_fn,
) -> None:
    st.markdown("#### 📊 Key Result Updates")
    needing_update = cached_get_krs_needing_checkin_fn(
        user_id=username,
        cycle_id=cycle_id,
        days_threshold=7,
    )

    if not needing_update:
        st.success("🎉 All Key Results are up to date!")
    else:
        for i, kr in enumerate(needing_update):
            with st.expander(f"📊 {kr.title}", expanded=(i == 0)):
                st.caption(f"Current: {kr.current_value} | Target: {kr.target_value}")

                ai_key = f"ai_sugg_{kr.id}"
                if st.button("✨ Get AI Estimate", key=f"btn_ai_{kr.id}"):
                    with st.spinner("Analyzing..."):
                        from src.services.ai_service import analyze_node

                        res = analyze_node(
                            kr.id,
                            "KEY_RESULT",
                            actor_username=username,
                        )
                        if "error" not in res:
                            st.session_state[ai_key] = res.get("analysis", {})
                        else:
                            st.error(res["error"])

                sugg = st.session_state.get(ai_key)
                if sugg:
                    st.info(f"**AI Recommendation:** {sugg['suggested_current_value']}")
                    if st.button("Apply Suggestion", key=f"apply_{kr.id}"):
                        st.session_state[f"val_{kr.id}"] = float(
                            sugg["suggested_current_value"]
                        )
                        st.rerun()

                st.markdown("---")
                st.markdown("**🔬 Variation Classification**")
                st.caption(
                    "Every check-in must classify what type of variation explains this result."
                )

                var_type_key = f"var_type_{kr.id}"
                exp_cache_key = f"active_exps_{kr.id}"

                if var_type_key not in st.session_state:
                    st.session_state[var_type_key] = "Common Cause"

                variation = st.radio(
                    "What type of variation?",
                    ["Common Cause", "Special Cause"],
                    key=var_type_key,
                    horizontal=True,
                    help="Common cause = system behavior we can experiment on. Special cause = exceptional one-time event.",
                )

                experiment_id_to_link = None
                special_cause_text = None

                if variation == "Special Cause":
                    st.info(
                        "📍 Special causes are exceptional events. Describe what happened."
                    )
                    special_cause_text = st.text_input(
                        "Special cause note (required, min 5 chars)",
                        placeholder="e.g., Customer outage, team member emergency",
                        key=f"special_note_{kr.id}",
                        max_chars=200,
                    )
                else:
                    st.info(
                        "🔬 Common causes reflect system behavior. Link to an active experiment if one exists."
                    )

                    if exp_cache_key not in st.session_state:
                        try:
                            st.session_state[exp_cache_key] = (
                                get_active_experiments_for_kr(
                                    kr.id,
                                    actor_username=username,
                                )
                            )
                        except PermissionError:
                            st.session_state[exp_cache_key] = []

                    active_exps = st.session_state.get(exp_cache_key, [])

                    if active_exps:
                        exp_ids = [None]
                        exp_labels = {None: "None (no experiment this week)"}
                        for experiment in active_exps:
                            exp_id = getattr(experiment, "id", None)
                            if exp_id is None:
                                continue
                            exp_id = int(exp_id)
                            exp_ids.append(exp_id)
                            status_badge = (
                                "🟢"
                                if experiment.status == ExperimentStatus.RUNNING
                                else "⚪"
                            )
                            hypothesis = experiment.hypothesis or ""
                            hypothesis_excerpt = (
                                f"{hypothesis[:50]}..."
                                if len(hypothesis) > 50
                                else hypothesis
                            )
                            exp_labels[exp_id] = (
                                f"{status_badge} {hypothesis_excerpt} | #{exp_id}"
                            )

                        selected_exp_id = st.selectbox(
                            "Link to active experiment",
                            options=exp_ids,
                            format_func=lambda eid: exp_labels.get(
                                eid, f"Experiment #{eid}"
                            ),
                            key=f"exp_select_{kr.id}",
                        )
                        experiment_id_to_link = (
                            int(selected_exp_id)
                            if selected_exp_id is not None
                            else None
                        )
                    else:
                        st.warning("No active experiments for this KR.")

                        show_exp_form_key = f"show_exp_form_{kr.id}"
                        if st.button(
                            "🔬 Start New Experiment", key=f"btn_new_exp_{kr.id}"
                        ):
                            st.session_state[show_exp_form_key] = True

                        if st.session_state.get(show_exp_form_key):
                            with st.form(f"new_exp_form_{kr.id}"):
                                st.markdown("**New Experiment**")
                                new_hyp = st.text_input(
                                    "Hypothesis *",
                                    placeholder="If we do X, then Y will improve",
                                )
                                new_change = st.text_area(
                                    "Change Description *",
                                    placeholder="What specific change will we make?",
                                )

                                c_dir, c_size = st.columns(2)
                                with c_dir:
                                    exp_dir = st.selectbox(
                                        "Expected Direction",
                                        ["UP", "DOWN"],
                                    )
                                with c_size:
                                    exp_size = st.number_input(
                                        "Expected Effect Size",
                                        min_value=0.0,
                                        value=10.0,
                                        step=5.0,
                                    )

                                if st.form_submit_button("Create & Start Experiment"):
                                    if new_hyp and new_change:
                                        try:
                                            new_exp = create_experiment(
                                                key_result_id=kr.id,
                                                cycle_id=cycle_id,
                                                hypothesis=new_hyp,
                                                change_description=new_change,
                                                actor_username=username,
                                                expected_effect_direction=ExpectedEffectDirection(
                                                    exp_dir
                                                ),
                                                expected_effect_size=exp_size,
                                            )
                                            update_experiment(
                                                new_exp.id,
                                                actor_username=username,
                                                status=ExperimentStatus.RUNNING,
                                            )

                                            if exp_cache_key in st.session_state:
                                                del st.session_state[exp_cache_key]
                                            del st.session_state[show_exp_form_key]
                                            st.success(
                                                "Experiment created and running!"
                                            )
                                            st.rerun()
                                        except PermissionError as exc:
                                            st.error(str(exc))
                                        except ValueError as exc:
                                            st.error(str(exc))
                                    else:
                                        st.error(
                                            "Hypothesis and change description are required."
                                        )

                st.markdown("---")
                with st.form(f"checkin_form_{kr.id}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_val_in = st.number_input(
                            "New Value",
                            value=st.session_state.get(
                                f"val_{kr.id}",
                                float(kr.current_value),
                            ),
                            key=f"inp_val_{kr.id}",
                        )
                    with c2:
                        conf = st.slider(
                            "Confidence (0-10)",
                            0,
                            10,
                            5,
                            key=f"conf_{kr.id}",
                        )

                    comment = st.text_area("What changed?", key=f"comm_{kr.id}")
                    if st.form_submit_button("✅ Update"):
                        try:
                            create_check_in(
                                kr.id,
                                new_val_in,
                                conf,
                                comment,
                                actor_username=username,
                                variation_type=VariationType.COMMON_CAUSE
                                if variation == "Common Cause"
                                else VariationType.SPECIAL_CAUSE,
                                special_cause_note=special_cause_text,
                                experiment_id=experiment_id_to_link,
                            )
                        except PermissionError as exc:
                            st.error(str(exc))
                            return
                        except ValueError as exc:
                            st.error(str(exc))
                            return
                        if ai_key in st.session_state:
                            del st.session_state[ai_key]
                        if exp_cache_key in st.session_state:
                            del st.session_state[exp_cache_key]
                        st.success("Check-in recorded!")
                        st.rerun()

    col_nav_2 = st.columns(2)
    if col_nav_2[0].button("⬅️ Back"):
        st.session_state.ritual_step = 1
        st.rerun()
    if col_nav_2[1].button("Next: Plan Week ➡️", type="primary"):
        st.session_state.ritual_step = 3
        st.rerun()


def _render_plan_next_week_step(
    username: str,
    *,
    cached_get_user_by_username_fn,
) -> None:
    st.markdown("#### 🎯 Planning Next Week")
    with st.form("planning_form"):
        p1 = st.text_input("Priority #1")
        p2 = st.text_input("Priority #2")
        p3 = st.text_input("Priority #3")
        if st.form_submit_button("🚀 Finish Ritual"):
            user_obj_p = cached_get_user_by_username_fn(username)
            if user_obj_p:
                sd = utc_now_naive()
                ed = sd + timedelta(days=7)
                create_weekly_plan(
                    user_obj_p.id,
                    sd,
                    ed,
                    p1,
                    p2,
                    p3,
                    actor_username=username,
                )
            st.toast("Weekly Ritual Complete!")
            del st.session_state.ritual_step
            if "ritual_summary" in st.session_state:
                del st.session_state.ritual_summary
            st.rerun()
    if st.button("⬅️ Back", key="ritual_back_3"):
        st.session_state.ritual_step = 2
        st.rerun()


def render_weekly_ritual_dialog_content(
    username: str,
    *,
    cached_get_user_by_username_fn,
    cached_get_work_logs_by_range_fn,
    cached_get_user_retrospectives_fn,
    cached_get_krs_needing_checkin_fn,
) -> None:
    """Render weekly ritual dialog body."""
    _render_weekly_ritual_chrome()

    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle first.")
        return

    if "ritual_step" not in st.session_state:
        st.session_state.ritual_step = 1

    step = st.session_state.ritual_step
    _render_ritual_stepper(step)

    if step == 1:
        _render_review_week_step(
            username,
            cycle_id,
            cached_get_user_by_username_fn=cached_get_user_by_username_fn,
            cached_get_work_logs_by_range_fn=cached_get_work_logs_by_range_fn,
            cached_get_user_retrospectives_fn=cached_get_user_retrospectives_fn,
        )
    elif step == 2:
        _render_update_krs_step(
            username,
            cycle_id,
            cached_get_krs_needing_checkin_fn=cached_get_krs_needing_checkin_fn,
        )
    elif step == 3:
        _render_plan_next_week_step(
            username,
            cached_get_user_by_username_fn=cached_get_user_by_username_fn,
        )
