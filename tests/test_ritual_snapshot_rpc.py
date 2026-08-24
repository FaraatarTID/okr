"""Tests for the consolidated Check-In snapshot (ritual.snapshot).

Covers:
- Authorization gate (_validate_supabase_read_scope) for the snapshot branch.
- RPC-first dispatch with SQLSTATE 42883-only fallback to concurrent fan-out.
- Response mapping from the RPC jsonb payload to the legacy top-level keys.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _make_main(
    *,
    supabase_mode: bool = True,
    scope: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a minimal `main` stand-in matching read_query_helpers' usage."""
    main = MagicMock()

    class _HTTPException(Exception):
        def __init__(self, status_code: int = 400, detail: str = "") -> None:
            super().__init__(detail or f"HTTP_{status_code}")
            self.status_code = status_code
            self.detail = detail

    main.HTTPException = _HTTPException

    def raise_http(status_code: int, detail: str = "") -> None:
        raise _HTTPException(status_code, detail)

    # _coerce_int passthrough for ints
    main._coerce_int = lambda value, field_name="value": int(value)

    # Scope resolution returns a member scope by default.
    resolved = scope or {
        "is_admin": False,
        "role": "member",
        "actor_id": 1,
        "actor_username": "alice",
        "owner_ids": {1},
        "usernames": {"alice"},
    }
    main._resolve_scope_for_actor = lambda actor: resolved

    def require_allowed_user_id(sc: dict, user_id: int) -> None:
        if not bool(sc.get("is_admin", False)):
            if int(user_id) not in {int(v) for v in (sc.get("owner_ids") or set())}:
                raise_http(403, "Actor is not authorized.")

    def require_allowed_username(sc: dict, username: str) -> None:
        if not bool(sc.get("is_admin", False)):
            if username not in {str(v) for v in (sc.get("usernames") or set())}:
                raise_http(403, "Actor is not authorized.")

    main._require_allowed_user_id = require_allowed_user_id
    main._require_allowed_username = require_allowed_username

    main.is_supabase_api_mode_enabled = lambda: supabase_mode
    main.logger = MagicMock()
    return main


@pytest.fixture()
def no_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the RPC path to report a missing function (42883-style)."""
    import src.services.supabase_api_mode_read as read_mod

    def _raise_missing(*, kind: str, params: dict, actor: str) -> dict:
        exc = Exception(
            'Supabase API error (ritual.snapshot): function fn_ritual_snapshot '
            "does not exist (SQLSTATE 42883)"
        )
        exc.status_code = 500  # type: ignore[attr-defined]
        exc.detail = str(exc)  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(
        read_mod, "read_query_via_supabase_api", _raise_missing, raising=False
    )


def _snapshot_payload() -> dict[str, Any]:
    return {
        "key_results": [{"id": 10, "title": "KR A"}],
        "weekly_plan": {"id": 2, "priority_1": "P1"},
        "retros": [{"id": 3}],
        "work_logs": [{"id": 4}],
        "experiments": [{"id": 5}],
    }


def test_snapshot_rpc_path_maps_sections() -> None:
    """RPC payload sections map onto the legacy top-level response keys."""
    import backend_app.read_query_helpers as rqh

    main = _make_main()
    main.read_query_via_supabase_api = lambda **kwargs: {
        "snapshot": _snapshot_payload()
    }
    result = rqh.read_query_payload(
            kind="ritual.snapshot",
            params={
                "user_id": 1,
                "cycle_id": 1,
                "days_threshold": 7,
                "date": "2026-08-24T00:00:00Z",
                "window_start": "2026-08-17T00:00:00Z",
                "window_end": "2026-08-24T00:00:00Z",
            },
            actor="alice",
            main=main,
        )

    assert result["key_results"] == [{"id": 10, "title": "KR A"}]
    assert result["weekly_plan"]["priority_1"] == "P1"
    assert result["retros"] == [{"id": 3}]
    assert result["work_logs"] == [{"id": 4}]
    assert result["experiments"] == [{"id": 5}]


def test_snapshot_out_of_scope_user_id_rejected_before_dispatch() -> None:
    """A user_id outside the caller's scope must fail before any dispatch."""
    import backend_app.read_query_helpers as rqh

    main = _make_main()  # alice's scope: owner_ids={1}
    dispatched = {"called": False}

    def _spy(**kwargs: Any) -> dict:
        dispatched["called"] = True
        return {"snapshot": {}}

    main.read_query_via_supabase_api = _spy
    with pytest.raises(Exception) as excinfo:
            rqh.read_query_payload(
                kind="ritual.snapshot",
                params={
                    "user_id": 99,  # Bob's id — outside Alice's scope
                    "cycle_id": 1,
                    "days_threshold": 7,
                    "date": "2026-08-24T00:00:00Z",
                    "window_start": "2026-08-17T00:00:00Z",
                    "window_end": "2026-08-24T00:00:00Z",
                },
                actor="alice",
                main=main,
            )

    assert dispatched["called"] is False
    assert "403" in str(excinfo.value) or "not authorized" in str(excinfo.value)


def test_snapshot_falls_back_on_missing_function_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a missing-function failure triggers the concurrent fan-out."""
    import backend_app.read_query_helpers as rqh

    fanout_calls: list[str] = []

    def _dispatch(**kwargs: Any) -> dict:
        kind = str(kwargs.get("kind") or "")
        if kind == "ritual.snapshot":
            # Match production: read_query_via_supabase_api raises ValueError
            # with SQLSTATE 42883 in the message when the function is missing.
            raise ValueError(
                "Supabase API error (ritual.snapshot): function missing "
                "(SQLSTATE 42883): function fn_ritual_snapshot does not exist"
            )
        fanout_calls.append(kind)
        # Minimal per-kind payloads for the fallback path.
        return {
            "krs.needing_checkin": {"key_results": [{"id": 10}]},
            "weekly_plan.active": {"weekly_plan": None},
            "retros.user": {"retros": []},
            "work_logs.by_range": {"work_logs": []},
            "experiments.for_retro_window": {"experiments": []},
        }.get(kind, {})

    main = _make_main()
    main.read_query_via_supabase_api = _dispatch
    result = rqh.read_query_payload(
        kind="ritual.snapshot",
        params={
            "user_id": 1,
            "cycle_id": 1,
            "days_threshold": 7,
            "date": "2026-08-24T00:00:00Z",
            "window_start": "2026-08-17T00:00:00Z",
            "window_end": "2026-08-24T00:00:00Z",
        },
        actor="alice",
        main=main,
    )

    assert sorted(fanout_calls) == [
        "experiments.for_retro_window",
        "krs.needing_checkin",
        "retros.user",
        "weekly_plan.active",
        "work_logs.by_range",
    ]
    assert result["key_results"] == [{"id": 10}]


def test_snapshot_propagates_non_42883_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorization/other RPC failures must propagate, never fall back."""
    import backend_app.read_query_helpers as rqh

    fanout_calls: list[str] = []

    def _deny(**kwargs: Any) -> dict:
        kind = str(kwargs.get("kind") or "")
        if kind == "ritual.snapshot":
            exc = Exception("permission denied for function fn_ritual_snapshot")
            exc.status_code = 500  # type: ignore[attr-defined]
            exc.detail = str(exc)  # type: ignore[attr-defined]
            raise exc
        fanout_calls.append(kind)
        return {}

    main = _make_main()
    main.read_query_via_supabase_api = _deny
    with pytest.raises(Exception) as excinfo:
        rqh.read_query_payload(
            kind="ritual.snapshot",
            params={
                "user_id": 1,
                "cycle_id": 1,
                "days_threshold": 7,
                "date": "2026-08-24T00:00:00Z",
                "window_start": "2026-08-17T00:00:00Z",
                "window_end": "2026-08-24T00:00:00Z",
            },
            actor="alice",
            main=main,
        )

    assert "permission denied" in str(excinfo.value)
    assert not fanout_calls  # fallback must NOT engage on non-42883 errors
