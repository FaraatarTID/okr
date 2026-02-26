"""Weekly ritual KR check-in step helpers.

This module extracts the heavy "Step 2: Update KRs" flow from
`src.ui.dialogs_ritual_helpers` to keep the ritual orchestration module small.
"""

from __future__ import annotations

import streamlit as st

from src.crud import (
    create_check_in,
    create_experiment,
    get_active_experiments_for_kr,
    update_experiment,
)
from src.models import (
    ExperimentStatus,
    ExpectedEffectDirection,
    VariationType,
)


def _render_ai_estimate_controls(kr, username: str, ai_key: str) -> None:
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

    suggestion = st.session_state.get(ai_key)
    if suggestion:
        st.info(f"**AI Recommendation:** {suggestion['suggested_current_value']}")
        if st.button("Apply Suggestion", key=f"apply_{kr.id}"):
            st.session_state[f"val_{kr.id}"] = float(
                suggestion["suggested_current_value"]
            )
            st.rerun()


def _render_new_experiment_form(
    *,
    kr,
    cycle_id: int,
    username: str,
    exp_cache_key: str,
    show_exp_form_key: str,
) -> None:
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
                        expected_effect_direction=ExpectedEffectDirection(exp_dir),
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
                    st.success("Experiment created and running!")
                    st.rerun()
                except PermissionError as exc:
                    st.error(str(exc))
                except ValueError as exc:
                    st.error(str(exc))
            else:
                st.error("Hypothesis and change description are required.")


def _render_common_cause_experiment_linking(
    *,
    kr,
    cycle_id: int,
    username: str,
    exp_cache_key: str,
) -> int | None:
    st.info(
        "🔬 Common causes reflect system behavior. Link to an active experiment if one exists."
    )

    if exp_cache_key not in st.session_state:
        try:
            st.session_state[exp_cache_key] = get_active_experiments_for_kr(
                kr.id,
                actor_username=username,
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
                "🟢" if experiment.status == ExperimentStatus.RUNNING else "⚪"
            )
            hypothesis = experiment.hypothesis or ""
            hypothesis_excerpt = (
                f"{hypothesis[:50]}..." if len(hypothesis) > 50 else hypothesis
            )
            exp_labels[exp_id] = f"{status_badge} {hypothesis_excerpt} | #{exp_id}"

        selected_exp_id = st.selectbox(
            "Link to active experiment",
            options=exp_ids,
            format_func=lambda eid: exp_labels.get(eid, f"Experiment #{eid}"),
            key=f"exp_select_{kr.id}",
        )
        return int(selected_exp_id) if selected_exp_id is not None else None

    st.warning("No active experiments for this KR.")

    show_exp_form_key = f"show_exp_form_{kr.id}"
    if st.button("🔬 Start New Experiment", key=f"btn_new_exp_{kr.id}"):
        st.session_state[show_exp_form_key] = True

    if st.session_state.get(show_exp_form_key):
        _render_new_experiment_form(
            kr=kr,
            cycle_id=cycle_id,
            username=username,
            exp_cache_key=exp_cache_key,
            show_exp_form_key=show_exp_form_key,
        )

    return None


def _render_variation_controls(*, kr, cycle_id: int, username: str):
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
        st.info("📍 Special causes are exceptional events. Describe what happened.")
        special_cause_text = st.text_input(
            "Special cause note (required, min 5 chars)",
            placeholder="e.g., Customer outage, team member emergency",
            key=f"special_note_{kr.id}",
            max_chars=200,
        )
    else:
        experiment_id_to_link = _render_common_cause_experiment_linking(
            kr=kr,
            cycle_id=cycle_id,
            username=username,
            exp_cache_key=exp_cache_key,
        )

    return variation, special_cause_text, experiment_id_to_link, exp_cache_key


def _render_checkin_form(
    *,
    kr,
    username: str,
    variation: str,
    special_cause_text: str | None,
    experiment_id_to_link: int | None,
    exp_cache_key: str,
    ai_key: str,
) -> bool:
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
                return True
            except ValueError as exc:
                st.error(str(exc))
                return True

            if ai_key in st.session_state:
                del st.session_state[ai_key]
            if exp_cache_key in st.session_state:
                del st.session_state[exp_cache_key]
            st.success("Check-in recorded!")
            st.rerun()

    return False


def _render_single_kr_update(
    *,
    kr,
    index: int,
    cycle_id: int,
    username: str,
) -> bool:
    with st.expander(f"📊 {kr.title}", expanded=(index == 0)):
        st.caption(f"Current: {kr.current_value} | Target: {kr.target_value}")

        ai_key = f"ai_sugg_{kr.id}"
        _render_ai_estimate_controls(kr, username, ai_key)

        variation, special_cause_text, experiment_id_to_link, exp_cache_key = (
            _render_variation_controls(
                kr=kr,
                cycle_id=cycle_id,
                username=username,
            )
        )

        return _render_checkin_form(
            kr=kr,
            username=username,
            variation=variation,
            special_cause_text=special_cause_text,
            experiment_id_to_link=experiment_id_to_link,
            exp_cache_key=exp_cache_key,
            ai_key=ai_key,
        )


def render_update_krs_step_content(
    username: str,
    cycle_id: int,
    *,
    cached_get_krs_needing_checkin_fn,
) -> None:
    """Render step 2 of weekly ritual: KR check-ins and experiment linkage."""
    st.markdown("#### 📊 Key Result Updates")
    needing_update = cached_get_krs_needing_checkin_fn(
        user_id=username,
        cycle_id=cycle_id,
        days_threshold=7,
    )

    if not needing_update:
        st.success("🎉 All Key Results are up to date!")
    else:
        for idx, kr in enumerate(needing_update):
            should_abort = _render_single_kr_update(
                kr=kr,
                index=idx,
                cycle_id=cycle_id,
                username=username,
            )
            if should_abort:
                return

    col_nav_2 = st.columns(2)
    if col_nav_2[0].button("⬅️ Back"):
        st.session_state.ritual_step = 1
        st.rerun()
    if col_nav_2[1].button("Next: Plan Week ➡️", type="primary"):
        st.session_state.ritual_step = 3
        st.rerun()
