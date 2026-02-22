from src.ui import atlas_focus_selection_helpers


class _FakeColumn:
    def __init__(self, *, buttons=None):
        self._buttons = dict(buttons or {})
        self.markdowns = []

    def button(self, _label, key=None, **_kwargs):
        return bool(self._buttons.get(key, False))

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))


class _FakeSt:
    def __init__(self, *, button_map=None, select_value=None):
        self._button_map = dict(button_map or {})
        self._select_value = select_value
        self.markdowns = []
        self.columns_objs = None

    def columns(self, *_args, **_kwargs):
        self.columns_objs = [
            _FakeColumn(buttons=self._button_map),
            _FakeColumn(buttons=self._button_map),
        ]
        return self.columns_objs

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def selectbox(self, *_args, **_kwargs):
        return self._select_value


def test_resolve_suggested_focus_candidate_prefers_valid_ai_state():
    session_state = {
        "atlas_ai_suggested_next": {
            "task_ref": "task_2",
            "scope": "My OKRs",
            "reason": "AI hint",
            "confidence": 88,
        }
    }
    index = {
        "task_1": {"progress": 10},
        "task_2": {"progress": 40},
    }
    ref, reason, conf, is_ai = atlas_focus_selection_helpers.resolve_suggested_focus_candidate(
        session_state=session_state,
        task_refs=["task_1", "task_2"],
        index=index,
        selected_scope="My OKRs",
        actor_id=1,
        health_index={},
        next_score_fn=lambda *_args, **_kwargs: 0,
    )
    assert ref == "task_2"
    assert reason == "AI hint"
    assert conf == 88
    assert is_ai is True


def test_resolve_suggested_focus_candidate_removes_stale_ai_and_falls_back():
    session_state = {
        "atlas_ai_suggested_next": {
            "task_ref": "task_9",
            "scope": "My OKRs",
        }
    }
    index = {
        "task_1": {"progress": 100},
        "task_2": {"progress": 20},
    }
    ref, reason, conf, is_ai = atlas_focus_selection_helpers.resolve_suggested_focus_candidate(
        session_state=session_state,
        task_refs=["task_1", "task_2"],
        index=index,
        selected_scope="My OKRs",
        actor_id=1,
        health_index={},
        next_score_fn=lambda meta, *_args, **_kwargs: int(meta.get("progress") or 0),
    )
    assert ref == "task_2"
    assert reason is None
    assert conf is None
    assert is_ai is False
    assert "atlas_ai_suggested_next" not in session_state


def test_render_suggested_focus_banner_sets_focus_on_use_suggested():
    fake_st = _FakeSt(button_map={"atlas_top_suggest_focus_task_1": True})
    session_state = {}
    reruns = []

    rendered = atlas_focus_selection_helpers.render_suggested_focus_banner(
        st_module=fake_st,
        session_state=session_state,
        suggested_focus_ref="task_1",
        suggested_focus_reason=None,
        suggested_focus_confidence=91,
        suggested_focus_is_ai=True,
        index={"task_1": {"title": "Task One"}},
        actor_id=1,
        health_index={"task_1": {"kind": "risk"}},
        type_icons={"TASK": "📝"},
        escape_html_fn=lambda text: text,
        suggested_reason_fn=lambda *_args, **_kwargs: "Needs care",
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert rendered is True
    assert session_state["atlas_focus_task_ref"] == "task_1"
    assert session_state["atlas_selected_ref"] == "task_1"
    assert reruns == ["rerun"]
    assert any("AI confidence: 91%" in item for item in fake_st.markdowns)


def test_render_focus_task_picker_updates_selection_and_reruns():
    fake_st = _FakeSt(select_value="task_2")
    session_state = {}
    reruns = []

    picked = atlas_focus_selection_helpers.render_focus_task_picker(
        st_module=fake_st,
        session_state=session_state,
        focus_task_ref="task_1",
        task_refs=["task_1", "task_2"],
        index={
            "task_1": {"title": "Task A", "owner_name": "Alice"},
            "task_2": {"title": "Task B", "owner_name": "Bob"},
        },
        type_icons={"TASK": "📝"},
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert picked == "task_2"
    assert session_state["atlas_focus_task_ref"] == "task_2"
    assert reruns == ["rerun"]
