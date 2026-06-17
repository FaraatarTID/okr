from __future__ import annotations

from types import SimpleNamespace

from src.ui import app_query_helpers
from src.ui import session_keys


def test_sync_to_query_params_serializes_supported_navigation_state():
    st = SimpleNamespace(
        query_params={
            "focus": "99",
            "stale": "keep",
        }
    )
    session_state = {
        "active_cycle_id": 12,
        session_keys.ACTIVE_REPORT_MODE: "Weekly",
        session_keys.NAV_STACK: ["goal_1", "invalid", "TASK:3"],
        session_keys.ATLAS_SELECTED_REF: "TASK:3",
        session_keys.ATLAS_SCOPE_SELECTOR: "My Team",
        session_keys.ATLAS_FOCUS_TASK_REF: "TASK:7",
        session_keys.ATLAS_JUMP_QUERY: "cross team",
        session_keys.ATLAS_MAP_LENS: "Branch",
    }

    app_query_helpers.sync_to_query_params(st=st, session_state=session_state)

    assert st.query_params["cycle"] == "12"
    assert st.query_params["mode"] == "Weekly"
    assert st.query_params["nav"] == "goal_1,task_3"
    assert st.query_params["sel"] == "task_3"
    assert st.query_params["scope"] == "My Team"
    assert st.query_params["ft"] == "task_7"
    assert st.query_params["jump"] == "cross team"
    assert st.query_params["lens"] == "Branch"
    assert "focus" not in st.query_params
    assert st.query_params["stale"] == "keep"


def test_restore_from_query_params_restores_scalar_and_nav_stack_state():
    st = SimpleNamespace(
        query_params={
            "cycle": "5",
            "mode": "Daily",
            "focus": "41",
            "timer": "200",
            "nav": "GOAL:1,bad,task_2,OBJECTIVE:3",
            "sel": "TASK:2",
            "scope": "All Users",
            "ft": "task_2",
            "jump": "alpha beta",
            "lens": "Scope",
        }
    )
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert session_state["active_cycle_id"] == 5
    assert session_state[session_keys.ACTIVE_REPORT_MODE] == "Daily"
    assert session_state[session_keys.ACTIVE_INSPECTOR_ID] == 41
    assert session_state[session_keys.ACTIVE_TIMER_NODE_ID] == 200
    assert session_state[session_keys.NAV_STACK] == ["goal_1", "task_2", "objective_3"]
    assert session_state[session_keys.ATLAS_SELECTED_REF] == "task_2"
    assert session_state[session_keys.ATLAS_SCOPE_SELECTOR] == "All Users"
    assert session_state[session_keys.ATLAS_FOCUS_TASK_REF] == "task_2"
    assert session_state[session_keys.ATLAS_JUMP_QUERY] == "alpha beta"
    assert session_state[session_keys.ATLAS_MAP_LENS] == "Scope"


def test_restore_from_query_params_caps_nav_stack_length():
    nav_items = ",".join([f"task_{idx}" for idx in range(1, 31)])
    st = SimpleNamespace(query_params={"nav": nav_items})
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert len(session_state[session_keys.NAV_STACK]) == 12
    assert session_state[session_keys.NAV_STACK][0] == "task_1"
    assert session_state[session_keys.NAV_STACK][-1] == "task_12"


def test_restore_from_query_params_ignores_invalid_scalar_values():
    st = SimpleNamespace(
        query_params={
            "cycle": "0",
            "mode": "UnknownMode",
            "focus": "TASK:0",
            "timer": "-1",
            "sel": "bad-ref",
            "ft": "goal_9",
            "jump": " " * 5,
            "lens": "Tree",
        }
    )
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert "active_cycle_id" not in session_state
    assert session_keys.ACTIVE_REPORT_MODE not in session_state
    assert session_keys.ACTIVE_INSPECTOR_ID not in session_state
    assert session_keys.ACTIVE_TIMER_NODE_ID not in session_state
    assert session_keys.ATLAS_SELECTED_REF not in session_state
    assert session_keys.ATLAS_FOCUS_TASK_REF not in session_state
    assert session_keys.ATLAS_JUMP_QUERY not in session_state
    assert session_keys.ATLAS_MAP_LENS not in session_state


def test_restore_from_query_params_accepts_underscore_typed_focus_id():
    st = SimpleNamespace(query_params={"focus": "task_21"})
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert session_state[session_keys.ACTIVE_INSPECTOR_ID] == "task_21"


def test_sync_to_query_params_drops_invalid_scalar_values():
    st = SimpleNamespace(
        query_params={
            "cycle": "5",
            "mode": "Weekly",
            "focus": "18",
            "timer": "3",
            "sel": "goal_1",
            "scope": "My Team",
            "ft": "task_3",
            "jump": "old",
            "lens": "Scope",
        }
    )
    session_state = {
        "active_cycle_id": -10,
        session_keys.ACTIVE_REPORT_MODE: "UnknownMode",
        session_keys.ACTIVE_INSPECTOR_ID: "TASK:0",
        session_keys.ACTIVE_TIMER_NODE_ID: 0,
        session_keys.NAV_STACK: [],
        session_keys.ATLAS_SELECTED_REF: "task_0",
        session_keys.ATLAS_SCOPE_SELECTOR: " " * 4,
        session_keys.ATLAS_FOCUS_TASK_REF: "goal_9",
        session_keys.ATLAS_JUMP_QUERY: " " * 4,
        session_keys.ATLAS_MAP_LENS: "Tree",
    }

    app_query_helpers.sync_to_query_params(st=st, session_state=session_state)

    assert "cycle" not in st.query_params
    assert "mode" not in st.query_params
    assert "focus" not in st.query_params
    assert "timer" not in st.query_params
    assert "sel" not in st.query_params
    assert "scope" not in st.query_params
    assert "ft" not in st.query_params
    assert "jump" not in st.query_params
    assert "lens" not in st.query_params


def test_restore_from_query_params_ignores_overlong_scope_label():
    st = SimpleNamespace(query_params={"scope": "A" * 161})
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert session_keys.ATLAS_SCOPE_SELECTOR not in session_state


def test_restore_from_query_params_canonicalizes_colon_refs():
    st = SimpleNamespace(query_params={"sel": "TASK:9", "ft": "TASK:11"})
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert session_state[session_keys.ATLAS_SELECTED_REF] == "task_9"
    assert session_state[session_keys.ATLAS_FOCUS_TASK_REF] == "task_11"


def test_restore_from_query_params_ignores_overlong_jump_query():
    st = SimpleNamespace(query_params={"jump": "x" * 121})
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert session_keys.ATLAS_JUMP_QUERY not in session_state


def test_restore_from_query_params_ignores_invalid_map_lens():
    st = SimpleNamespace(query_params={"lens": "Tree"})
    session_state: dict[str, object] = {}

    app_query_helpers.restore_from_query_params(st=st, session_state=session_state)

    assert session_keys.ATLAS_MAP_LENS not in session_state
