from types import SimpleNamespace

from src.ui import atlas_focus_map_shell_helpers


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePlaceholder:
    def container(self):
        return _FakeCtx()


class _FakeSt:
    def __init__(self):
        self.markdowns = []
        self.captions = []
        self.tabs_calls = []
        self.columns_calls = []
        self.container_count = 0

    def tabs(self, labels):
        self.tabs_calls.append(list(labels))
        return ("focus_tab", "inspector_tab")

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def caption(self, value):
        self.captions.append(str(value))

    def empty(self):
        return _FakePlaceholder()

    def container(self):
        self.container_count += 1
        return SimpleNamespace(name=f"container_{self.container_count}")

    def columns(self, spec, **kwargs):
        self.columns_calls.append((list(spec), dict(kwargs)))
        return [SimpleNamespace(name="col_0"), SimpleNamespace(name="col_1")]


def test_create_workspace_tabs_uses_expected_labels():
    fake_st = _FakeSt()
    focus_tab, inspector_tab = atlas_focus_map_shell_helpers.create_workspace_tabs(
        fake_st
    )
    assert focus_tab == "focus_tab"
    assert inspector_tab == "inspector_tab"
    assert fake_st.tabs_calls == [["Focus Map", "Inspector"]]


def test_render_focus_map_shell_desktop_uses_columns_and_nav_labels():
    fake_st = _FakeSt()
    map_chart_area, map_sidebar_area = (
        atlas_focus_map_shell_helpers.render_focus_map_shell(
            st_module=fake_st,
            selected_meta={"path": ["goal_1", "objective_2", "missing_3"]},
            node_lookup={},
            type_icons={"GOAL": "🎯", "OBJECTIVE": "🧭"},
            get_node_details_fn=lambda ref, **_kwargs: (
                ("GOAL", "Goal A")
                if ref == "goal_1"
                else ("OBJECTIVE", "Objective B")
                if ref == "objective_2"
                else (None, "")
            ),
            escape_html_fn=lambda text: f"ESC:{text}",
            is_mobile_request=False,
        )
    )

    assert map_chart_area.name == "col_0"
    assert map_sidebar_area.name == "col_1"
    assert fake_st.columns_calls == [([2.25, 1.05], {"gap": "large"})]
    assert any("Focus Map" in value for value in fake_st.markdowns)
    assert any(
        "ESC:Home > 🎯 Goal A > 🧭 Objective B" in value for value in fake_st.markdowns
    )
    assert fake_st.captions == ["Navigate hierarchy and pick your next move."]


def test_render_focus_map_shell_mobile_uses_containers():
    fake_st = _FakeSt()
    map_chart_area, map_sidebar_area = (
        atlas_focus_map_shell_helpers.render_focus_map_shell(
            st_module=fake_st,
            selected_meta={"path": []},
            node_lookup={},
            type_icons={},
            get_node_details_fn=lambda *_args, **_kwargs: (None, ""),
            escape_html_fn=lambda text: text,
            is_mobile_request=True,
        )
    )

    assert map_chart_area.name == "container_1"
    assert map_sidebar_area.name == "container_2"
    assert fake_st.columns_calls == []
    assert fake_st.container_count == 2
