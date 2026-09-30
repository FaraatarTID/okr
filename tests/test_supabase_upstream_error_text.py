"""Upstream (PostgREST/Postgres) error text must not travel inside the exceptions the API turns into HTTP details.

`main_mutation_handlers` and `read_query_helpers` return `str(exc)` of a `ValueError` as an HTTP 400/404 detail. Postgres
messages name constraints, tables, columns and key values, so the Supabase helpers log that text and raise a fixed message
with the status only. `ritual.snapshot` is the exception that needs care: `read_query_helpers` decides on the fan-out
fallback by looking for `42883` or `fn_ritual_snapshot` in the message, so only the missing-function message may contain them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

import src.services.supabase_api_mode_nodes as nodes
import src.services.supabase_api_mode_operations as ops
import src.services.supabase_api_mode_read as read
import src.services.supabase_api_mode_transport as transport

UPSTREAM = 'duplicate key value violates unique constraint "task_pkey_secret_name"'
UPSTREAM_DETAIL = "Key (id)=(5) already exists."


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key-for-unit-tests")
    monkeypatch.setattr(transport, "_CYCLE_OWNER_COLUMN_SUPPORTED", True)


def test_create_task_failure_does_not_carry_upstream_text(monkeypatch, caplog):
    monkeypatch.setattr(
        nodes,
        "_rest_select",
        lambda *a, **k: (200, [{"id": 1, "owner_id": 1, "team_id": 1}]),
    )
    monkeypatch.setattr(
        nodes,
        "_rest_insert",
        lambda table, payload=None: (
            409,
            {"code": "23505", "message": UPSTREAM, "details": UPSTREAM_DETAIL},
        ),
    )

    with caplog.at_level(logging.ERROR, logger=nodes.logger.name):
        with pytest.raises(ValueError) as caught:
            nodes.create_task_via_supabase_api(
                key_result_id=1, title="t", actor_username="alice"
            )

    assert str(caught.value) == "Supabase API error (create_task): 409"
    assert "task_pkey_secret_name" in caplog.text  # still diagnosable from the log


def _update_cycle():
    return ops.update_cycle_via_supabase_api(
        cycle_id=1,
        title="Q1",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
        is_active=True,
        actor_username="admin",
    )


def test_cycle_activation_rpc_failure_does_not_carry_upstream_text(monkeypatch, caplog):
    monkeypatch.setattr(
        ops,
        "_rest_rpc",
        lambda name, args: (
            500,
            {"code": "XX000", "message": 'relation "private.cycle_lock" is broken'},
        ),
    )

    with caplog.at_level(logging.WARNING, logger=ops.logger.name):
        with pytest.raises(ValueError) as caught:
            _update_cycle()

    assert str(caught.value) == "Supabase API error (cycle/activate_rpc): 500"
    assert "private.cycle_lock" in caplog.text


def _ritual(monkeypatch, status, payload):
    monkeypatch.setattr(read, "_rest_rpc", lambda name, args: (status, payload))
    return read.read_query_via_supabase_api(
        kind="ritual.snapshot",
        params={
            "user_id": 1,
            "cycle_id": 1,
            "window_start": "2026-08-17T00:00:00Z",
            "window_end": "2026-08-24T00:00:00Z",
            "days_threshold": 7,
            "date": "2026-08-24T00:00:00Z",
        },
        actor="alice",
    )


def test_ritual_snapshot_http_error_does_not_carry_upstream_text(monkeypatch, caplog):
    payload = {
        "code": "42P01",
        "message": 'relation "internal_ritual_cache" does not exist',
    }

    with caplog.at_level(logging.WARNING, logger=read.logger.name):
        with pytest.raises(ValueError) as caught:
            _ritual(monkeypatch, 400, payload)

    assert str(caught.value) == "Supabase API error (ritual.snapshot): HTTP 400"
    assert "internal_ritual_cache" in caplog.text


@pytest.mark.parametrize(
    "status,payload",
    [
        (
            404,
            {
                "code": "PGRST202",
                "message": "Could not find the function public.fn_ritual_snapshot",
            },
        ),
        (
            404,
            {
                "code": "42883",
                "message": "function fn_ritual_snapshot(text) does not exist",
            },
        ),
    ],
)
def test_ritual_snapshot_missing_function_still_signals_the_fallback(
    monkeypatch, status, payload
):
    with pytest.raises(ValueError) as caught:
        _ritual(monkeypatch, status, payload)

    text = str(caught.value)
    assert "42883" in text  # read_query_helpers matches this to fall back
    assert "fn_ritual_snapshot" not in text  # and the upstream text is not echoed


def test_ritual_snapshot_permission_error_no_longer_looks_like_a_missing_function(
    monkeypatch,
):
    # Before: the upstream text was appended, and "permission denied for function fn_ritual_snapshot" contained the
    # name that read_query_helpers treats as a missing-function marker, so an authorization failure engaged the fallback.
    payload = {
        "code": "42501",
        "message": "permission denied for function fn_ritual_snapshot",
    }

    with pytest.raises(ValueError) as caught:
        _ritual(monkeypatch, 403, payload)

    text = str(caught.value)
    assert "42883" not in text and "fn_ritual_snapshot" not in text


def test_weekly_plan_upsert_failure_does_not_carry_upstream_text(monkeypatch, caplog):
    monkeypatch.setattr(ops, "_rest_select", lambda *a, **k: (200, []))
    monkeypatch.setattr(
        ops,
        "_rest_insert",
        lambda table, payload=None: (
            409,
            {"code": "23505", "message": UPSTREAM, "hint": "internal hint"},
        ),
    )

    with caplog.at_level(logging.ERROR, logger=ops.logger.name):
        with pytest.raises(ValueError) as caught:
            ops.create_weekly_plan_via_supabase_api(
                user_id=1,
                start_date=datetime(2026, 8, 17, tzinfo=timezone.utc),
                end_date=datetime(2026, 8, 24, tzinfo=timezone.utc),
                p1="focus",
                actor_username="alice",
            )

    assert str(caught.value) == "Supabase API error (weekly_plan/upsert): 409"
    assert "task_pkey_secret_name" in caplog.text


def test_cycle_create_failure_does_not_carry_upstream_text(monkeypatch, caplog):
    monkeypatch.setattr(ops, "_rest_update", lambda *a, **k: (200, []))
    monkeypatch.setattr(
        ops,
        "_request_json_with_method",
        lambda *a, **k: (
            409,
            {"code": "23505", "message": UPSTREAM, "details": UPSTREAM_DETAIL},
        ),
    )

    with caplog.at_level(logging.ERROR, logger=ops.logger.name):
        with pytest.raises(ValueError) as caught:
            ops.create_cycle_via_supabase_api(
                title="Q4",
                start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
                end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
                actor_username="admin",
            )

    assert str(caught.value) == "Supabase API error (cycle/create): 409"
    assert "already exists" in caplog.text
