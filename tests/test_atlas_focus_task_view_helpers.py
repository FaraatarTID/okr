from types import SimpleNamespace

from src.ui import atlas_focus_task_view_helpers


class _FakeColumn:
    def __init__(self, *, segmented_value="25m", number_value=35):
        self.segmented_value = segmented_value
        self.number_value = number_value
        self.captions = []
        self.markdowns = []

    def caption(self, value):
        self.captions.append(str(value))

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def segmented_control(self, *_args, **_kwargs):
        return self.segmented_value

    def number_input(self, *_args, **_kwargs):
        return self.number_value


class _FakeSt:
    def __init__(self, *, segmented_value="25m", number_value=35):
        self.markdowns = []
        self._segmented_value = segmented_value
        self._number_value = number_value
        self.cols = None

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def columns(self, *_args, **_kwargs):
        self.cols = [
            _FakeColumn(
                segmented_value=self._segmented_value, number_value=self._number_value
            ),
            _FakeColumn(
                segmented_value=self._segmented_value, number_value=self._number_value
            ),
        ]
        return self.cols


def test_build_focus_path_joins_titles_in_order():
    focus_path = atlas_focus_task_view_helpers.build_focus_path(
        focus_meta={"path": ["goal_1", "kr_2"]},
        index={"goal_1": {"title": "Goal A"}, "kr_2": {"title": "KR B"}},
    )
    assert focus_path == "Goal A > KR B"


def test_render_focus_identity_outputs_path_title_and_description():
    fake_st = _FakeSt()
    atlas_focus_task_view_helpers.render_focus_identity(
        st_module=fake_st,
        focus_meta={
            "title": "Task X",
            "description": "Line1\nLine2",
            "path": ["task_1"],
        },
        focus_task=SimpleNamespace(description=""),
        index={"task_1": {"title": "Task X"}},
        type_icons={"TASK": "📝"},
        escape_html_fn=lambda text: f"ESC:{text}",
    )
    assert any("atlas-spotlight-path" in item for item in fake_st.markdowns)
    assert any("📝 ESC:Task X" in item for item in fake_st.markdowns)
    assert any("Line1<br>Line2" in item for item in fake_st.markdowns)


def test_render_focus_status_and_commit_controls_returns_target_minutes_custom():
    fake_st = _FakeSt(segmented_value="Custom", number_value=40)
    session_state = {"atlas_commit_preset": "Custom"}
    commit_calls = []

    spotlight_cols, target_minutes = (
        atlas_focus_task_view_helpers.render_focus_status_and_commit_controls(
            st_module=fake_st,
            session_state=session_state,
            focus_meta={"owner_name": "Alice"},
            focus_health={"source": "progress"},
            index={},
            health_index={},
            health_state_fn=lambda *_args, **_kwargs: {},
            attention_chip_html_fn=lambda **_kwargs: "<span>chip</span>",
            health_source_explanation_fn=lambda source: f"because:{source}",
            escape_html_fn=lambda text: text,
            commit_target_minutes_fn=lambda choice, custom=None: (
                commit_calls.append((choice, custom))
                or (
                    25
                    if choice == "25m"
                    else 50
                    if choice == "50m"
                    else int(custom or 35)
                )
            ),
        )
    )

    assert len(spotlight_cols) == 2
    assert target_minutes == 40
    assert ("Custom", 40) in commit_calls
    assert any("Owned by Alice" in item for item in spotlight_cols[0].captions)
    assert any("because:progress" in item for item in spotlight_cols[0].captions)
