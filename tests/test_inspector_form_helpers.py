from types import SimpleNamespace

from src.ui import inspector_form_helpers


class _FakeSt:
    def __init__(self, *, selectbox_value=None):
        self.selectbox_value = selectbox_value
        self.selectbox_calls = []
        self.info_calls = []

    def selectbox(self, label, options, index=0, format_func=None, key=None):
        self.selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "index": int(index),
                "key": str(key),
                "rendered": [format_func(opt) if format_func else opt for opt in options],
            }
        )
        if self.selectbox_value is not None:
            return self.selectbox_value
        return options[index]

    def info(self, value):
        self.info_calls.append(str(value))


def test_resolve_task_assignee_non_task_returns_none():
    fake_st = _FakeSt()
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "admin"},
        node=SimpleNamespace(assignee_id=7),
        node_type_upper="OBJECTIVE",
        node_id=5,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result is None
    assert fake_st.selectbox_calls == []


def test_resolve_task_assignee_admin_selects_current_index():
    fake_st = _FakeSt(selectbox_value=2)
    users = [
        SimpleNamespace(id=1, username="u1", display_name="User One"),
        SimpleNamespace(id=2, username="u2", display_name="User Two"),
    ]
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "admin"},
        node=SimpleNamespace(assignee_id=2),
        node_type_upper="TASK",
        node_id=99,
        get_all_users_fn=lambda: users,
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result == 2
    assert len(fake_st.selectbox_calls) == 1
    assert fake_st.selectbox_calls[0]["label"] == "Assign To"
    assert fake_st.selectbox_calls[0]["index"] == 1
    assert fake_st.selectbox_calls[0]["options"] == [1, 2]
    assert fake_st.selectbox_calls[0]["key"] == "assign_sel_99"


def test_resolve_task_assignee_manager_includes_manager_option():
    fake_st = _FakeSt()
    manager = SimpleNamespace(id=5, username="mgr", display_name="Manager")
    team = [SimpleNamespace(id=11, username="tm1", display_name="Team A")]
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "manager", "user_id": 5},
        node=SimpleNamespace(assignee_id=11),
        node_type_upper="TASK",
        node_id=77,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda uid: manager if uid == 5 else None,
        get_team_members_fn=lambda uid: team if uid == 5 else [],
    )
    assert result == 11
    assert len(fake_st.selectbox_calls) == 1
    assert fake_st.selectbox_calls[0]["options"] == [11, 5]


def test_resolve_task_assignee_member_shows_read_only_assigned():
    fake_st = _FakeSt()
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "member"},
        node=SimpleNamespace(
            assignee_id=3,
            assignee=SimpleNamespace(display_name="Assigned User"),
        ),
        node_type_upper="TASK",
        node_id=10,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result == 3
    assert fake_st.selectbox_calls == []
    assert fake_st.info_calls == ["👥 **Assigned To:** Assigned User"]


def test_resolve_task_assignee_member_shows_unassigned():
    fake_st = _FakeSt()
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "member"},
        node=SimpleNamespace(assignee_id=None, assignee=None),
        node_type_upper="TASK",
        node_id=10,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result is None
    assert fake_st.info_calls == ["👥 **Unassigned**"]
