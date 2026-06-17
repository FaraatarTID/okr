from src.ui import atlas_workspace_bootstrap_helpers


class _FakeSt:
    def __init__(self, *, button_value=False):
        self.button_value = bool(button_value)
        self.info_calls = []
        self.error_calls = []
        self.button_calls = []

    def info(self, message):
        self.info_calls.append(str(message))

    def error(self, message):
        self.error_calls.append(str(message))

    def button(self, label, key=None, type=None):
        self.button_calls.append((str(label), str(key), str(type)))
        return self.button_value


def test_bootstrap_returns_none_when_cycle_missing():
    fake_st = _FakeSt()
    result = atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap(
        st_module=fake_st,
        session_state={},
        username="alice",
        logger=None,
        resolve_actor_context_fn=lambda *_args, **_kwargs: (1, "admin"),
        build_scope_options_fn=lambda **_kwargs: {"My OKRs": [1]},
        ensure_scope_selection_fn=lambda *_args, **_kwargs: "My OKRs",
        resolve_scope_runtime_fn=lambda **_kwargs: {},
        ensure_selected_ref_fn=lambda *_args, **_kwargs: "goal_1",
        sync_selected_navigation_fn=lambda *_args, **_kwargs: {"goal_1"},
        team_members_loader=lambda _uid: [],
        all_users_loader=lambda: [],
        runtime_loader=lambda *_args, **_kwargs: {},
        canonical_owner_ids_key_fn=lambda _owner_ids: None,
        health_index_builder_fn=lambda _index: {},
        rerun_fn=lambda: None,
    )
    assert result is None
    assert fake_st.info_calls == ["Select a cycle to load the OKR workspace."]


def test_bootstrap_returns_none_when_actor_context_invalid():
    fake_st = _FakeSt()
    result = atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap(
        st_module=fake_st,
        session_state={"active_cycle_id": 7},
        username="alice",
        logger=None,
        resolve_actor_context_fn=lambda *_args, **_kwargs: (None, ""),
        build_scope_options_fn=lambda **_kwargs: {"My OKRs": [1]},
        ensure_scope_selection_fn=lambda *_args, **_kwargs: "My OKRs",
        resolve_scope_runtime_fn=lambda **_kwargs: {},
        ensure_selected_ref_fn=lambda *_args, **_kwargs: "goal_1",
        sync_selected_navigation_fn=lambda *_args, **_kwargs: {"goal_1"},
        team_members_loader=lambda _uid: [],
        all_users_loader=lambda: [],
        runtime_loader=lambda *_args, **_kwargs: {},
        canonical_owner_ids_key_fn=lambda _owner_ids: None,
        health_index_builder_fn=lambda _index: {},
        rerun_fn=lambda: None,
    )
    assert result is None
    assert fake_st.error_calls == ["User context is unavailable. Please log in again."]


def test_bootstrap_handles_empty_roots_and_create_goal_action():
    fake_st = _FakeSt(button_value=True)
    state = {"active_cycle_id": 9}
    reruns = []
    result = atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap(
        st_module=fake_st,
        session_state=state,
        username="alice",
        logger=None,
        resolve_actor_context_fn=lambda *_args, **_kwargs: (4, "manager"),
        build_scope_options_fn=lambda **_kwargs: {"My OKRs": [4]},
        ensure_scope_selection_fn=lambda *_args, **_kwargs: "My OKRs",
        resolve_scope_runtime_fn=lambda **_kwargs: {
            "index": {},
            "roots": [],
            "node_lookup": {"n": 1},
            "health_index": {},
            "runtime_token": "rt",
        },
        ensure_selected_ref_fn=lambda *_args, **_kwargs: None,
        sync_selected_navigation_fn=lambda *_args, **_kwargs: set(),
        team_members_loader=lambda _uid: [],
        all_users_loader=lambda: [],
        runtime_loader=lambda *_args, **_kwargs: {},
        canonical_owner_ids_key_fn=lambda _owner_ids: None,
        health_index_builder_fn=lambda _index: {},
        rerun_fn=lambda: reruns.append("rerun"),
    )
    assert result is None
    assert fake_st.info_calls == ["No goals found for this cycle and scope."]
    assert state["atlas_node_lookup"] == {"n": 1}
    assert state["add_mode_parent"] is None
    assert state["add_mode_type"] == "GOAL"
    assert reruns == ["rerun"]


def test_bootstrap_returns_context_on_happy_path():
    fake_st = _FakeSt()
    state = {"active_cycle_id": 3}
    calls = {}

    def _resolve_runtime(**kwargs):
        calls["runtime"] = kwargs
        return {
            "owner_ids": [5],
            "owner_ids_key": (5,),
            "index": {"goal_1": {"title": "Goal", "path": ["goal_1"]}},
            "roots": ["goal_1"],
            "node_lookup": {"goal_1": {"x": 1}},
            "health_index": {"goal_1": {"source": "memo"}},
            "runtime_token": "token-1",
        }

    result = atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap(
        st_module=fake_st,
        session_state=state,
        username="alice",
        logger=None,
        resolve_actor_context_fn=lambda *_args, **_kwargs: (5, "admin"),
        build_scope_options_fn=lambda **_kwargs: {"My OKRs": [5]},
        ensure_scope_selection_fn=lambda *_args, **_kwargs: "My OKRs",
        resolve_scope_runtime_fn=_resolve_runtime,
        ensure_selected_ref_fn=lambda *_args, **_kwargs: "goal_1",
        sync_selected_navigation_fn=lambda *_args, **_kwargs: {"goal_1"},
        team_members_loader=lambda _uid: [],
        all_users_loader=lambda: [],
        runtime_loader=lambda *_args, **_kwargs: {},
        canonical_owner_ids_key_fn=lambda owner_ids: tuple(owner_ids or []),
        health_index_builder_fn=lambda _index: {},
        rerun_fn=lambda: None,
    )

    assert result is not None
    assert result["cycle_id"] == 3
    assert result["actor_id"] == 5
    assert result["selected_scope"] == "My OKRs"
    assert result["scope_labels"] == ["My OKRs"]
    assert result["selected_ref"] == "goal_1"
    assert result["selected_path_refs"] == {"goal_1"}
    assert result["runtime_token"] == "token-1"
    assert state["atlas_node_lookup"] == {"goal_1": {"x": 1}}
    assert calls["runtime"]["cycle_id"] == 3
    assert calls["runtime"]["actor_username"] == "alice"
