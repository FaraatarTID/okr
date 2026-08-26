"""Regression tests for API-mode insert payloads.

Background: the live database has several NOT NULL columns WITHOUT server
defaults (e.g. ``user.created_at``, ``team.created_at``). SQLModel's Python-side
``default_factory`` is invisible to PostgREST, so API-mode create helpers must
send these columns explicitly. This bug class shipped twice before
(duration_minutes on work_log, created_at on user/team) because endpoint tests
mocked the create helpers entirely and never inspected the outgoing payload.

These tests capture the REAL payloads built by the supabase_api_mode helpers
(only the transport layer is faked) and assert that every NOT NULL / no-default
column of the target table is present in the payload.
"""

from __future__ import annotations

from typing import Any

import pytest


# Synthetic placeholder used only by this regression test. Not a real
# credential; matches the convention used elsewhere in the test suite
# (e.g. tests/test_e2e_playwright_spa_login_to_atlas.py).
_TEST_USER_PASSWORD = "test-only-placeholder-password"


class _CaptureInsert:
    """Fake _rest_insert that records the last payload per table."""

    def __init__(self) -> None:
        self.payloads: dict[str, dict[str, Any]] = {}

    def __call__(self, table: str, *, payload: dict[str, Any]):
        self.payloads[table] = payload
        return 201, [dict(payload, id=999)]


# Columns that are NOT NULL with no DB server default in the live schema.
# An API-mode INSERT missing any of these will fail with 23502 at runtime.
# (token_version has a DB default of 1, so it is not required. `role` is
# always sent by create_user_via_supabase_api via _role_for_storage.)
_REQUIRED_INSERT_COLUMNS: dict[str, set[str]] = {
    "user": {
        "username",
        "password_hash",
        "role",
        "must_change_password",
        "created_at",
        "is_active",
    },
    "team": {"name", "created_at"},
    "work_log": {"task_id", "start_time", "duration_minutes"},
}


@pytest.fixture()
def capture_insert(monkeypatch: pytest.MonkeyPatch) -> _CaptureInsert:
    import src.services.supabase_api_mode_operations as ops
    import src.services.supabase_api_mode_mutation as mutation

    cap = _CaptureInsert()
    monkeypatch.setattr(
        ops,
        "_rest_insert",
        lambda table, *, payload: cap(table, payload=payload),
    )
    monkeypatch.setattr(
        mutation,
        "_rest_insert",
        lambda table, *, payload: cap(table, payload=payload),
    )
    return cap


def _assert_required_columns(table: str, payload: dict[str, Any]) -> None:
    required = _REQUIRED_INSERT_COLUMNS.get(table, set())
    missing = sorted(required - set(payload.keys()))
    assert not missing, (
        f"API-mode INSERT into '{table}' is missing required column(s) "
        f"{missing}. These columns are NOT NULL without a server default; "
        f"PostgREST will reject the insert with 23502."
    )


def test_user_create_payload_includes_required_columns(capture_insert):
    from src.services.supabase_api_mode_operations import create_user_via_supabase_api

    create_user_via_supabase_api(
        username="regression-user",
        password=_TEST_USER_PASSWORD,
        role="manager",
        display_name="Regression User",
        manager_id=None,
        team_id=None,
        must_change_password=False,
        actor_username="admin",
    )

    payload = capture_insert.payloads.get("user")
    assert payload is not None
    _assert_required_columns("user", payload)
    # Role must be stored uppercase to match the live 'userrole' enum values.
    assert payload["role"] == "MANAGER"


def test_team_create_payload_includes_required_columns(capture_insert):
    from src.services.supabase_api_mode_mutation import create_team_via_supabase_api

    create_team_via_supabase_api(name="Regression Team", actor_username="admin")

    payload = capture_insert.payloads.get("team")
    assert payload is not None
    _assert_required_columns("team", payload)


def test_timer_start_payload_includes_required_columns(capture_insert, monkeypatch):
    monkeypatch.setattr(
        "src.services.supabase_api_mode_operations._rest_select",
        lambda table, query=None: (
            (200, [{"id": 1}]) if table == "task" else (200, [])
        ),
    )
    from src.services.supabase_api_mode_operations import start_timer_via_supabase_api

    start_timer_via_supabase_api(task_id=1, actor_username="alice")

    payload = capture_insert.payloads.get("work_log")
    assert payload is not None
    _assert_required_columns("work_log", payload)
