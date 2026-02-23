from src.ui import atlas_map_sidebar_ai_helpers


class _FakeSidebar:
    def __init__(self, *, buttons=None, toggles=None, slider_value=25):
        self._buttons = dict(buttons or {})
        self._toggles = dict(toggles or {})
        self._slider_value = slider_value
        self.progress_updates = []
        self.progress_cleared = False

    def markdown(self, _value, **_kwargs):
        return None

    def button(self, _label, key=None, **_kwargs):
        return bool(self._buttons.get(key, False))

    def toggle(self, _label, key=None, value=False, **_kwargs):
        return bool(self._toggles.get(key, value))

    def slider(self, _label, **_kwargs):
        return self._slider_value

    def progress(self, value, text=None, **_kwargs):
        self.progress_updates.append((float(value), text))
        sidebar = self

        class _Progress:
            def progress(self, next_value, text=None, **_kwargs):
                sidebar.progress_updates.append((float(next_value), text))

            def empty(self):
                sidebar.progress_cleared = True

        return _Progress()

    def info(self, _value):
        return None

    def success(self, _value):
        return None

    def warning(self, _value):
        return None

    def caption(self, _value):
        return None

    def expander(self, _label, **_kwargs):
        class _Expander:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Expander()


def test_render_ai_control_panel_default_and_custom_values():
    sidebar = _FakeSidebar(
        toggles={
            "atlas_ai_apply_overall_to_progress": True,
            "atlas_ai_sync_preview_mode": True,
            "atlas_ai_progress_allow_decrease": True,
        },
        slider_value=40,
    )
    state = {}
    apply_progress, preview_mode, max_delta, allow_decrease = (
        atlas_map_sidebar_ai_helpers.render_ai_control_panel(
            sidebar=sidebar,
            session_state=state,
            has_kr_refs=True,
        )
    )
    assert apply_progress is True
    assert preview_mode is True
    assert max_delta == 40
    assert allow_decrease is True


def test_handle_ai_progress_undo_action_expires_stale_payload():
    sidebar = _FakeSidebar(buttons={"atlas_ai_progress_undo_btn": True})
    session_state = {
        "atlas_ai_progress_undo": {
            "items": [{"kr_id": 1, "previous_progress": 20}],
            "at": 0.0,
        }
    }
    handled = atlas_map_sidebar_ai_helpers.handle_ai_progress_undo_action(
        sidebar=sidebar,
        session_state=session_state,
        username="alice",
        apply_ai_progress_undo_fn=lambda **_kwargs: {"restored": 1, "failed": []},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        recalculate_rollup_for_key_results_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
        now_fn=lambda: 5000.0,
    )
    assert handled is False
    assert "atlas_ai_progress_undo" not in session_state
