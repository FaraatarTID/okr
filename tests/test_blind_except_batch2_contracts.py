"""Behaviour of the handlers narrowed or annotated in the second blind-except review.

Each narrowed `except` used to catch `Exception`. These tests fix the inputs it has to keep absorbing, and
the audit tests fix the two decisions that are kept on purpose: a failed actor lookup or database sink must not
stop an audit event, and must not be silent.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from src import audit
from src.services import ai_provider, supabase_api_mode_transport as transport


@pytest.mark.parametrize(
    "value,expected",
    [
        ("7", 7),
        (7.9, 7),
        (None, 3),
        ("abc", 3),
        ([1], 3),
        ({}, 3),
        (float("inf"), 3),
        (float("nan"), 3),
    ],
)
def test_as_int_falls_back_for_unconvertible_values(value, expected):
    assert transport._as_int(value, 3) == expected


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "not a date", "2026-13-45", "2026-09-30T99:00:00"],
)
def test_parse_dt_returns_none_for_missing_or_invalid(value):
    assert transport._parse_dt(value) is None


def test_parse_dt_accepts_zulu_and_assumes_utc_for_naive():
    zulu = transport._parse_dt("2026-09-30T06:10:00Z")
    naive = transport._parse_dt("2026-09-30T06:10:00")

    assert zulu is not None and zulu.utcoffset().total_seconds() == 0
    assert naive is not None and naive.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "raw",
    [None, "", "  ", "{not json", "[1, 2]", '"text"', "123", "[" * 5000],
)
def test_atlas_snapshot_fields_absorb_bad_stored_analysis(raw):
    assert transport._atlas_extract_ai_snapshot_fields(raw) == (None, None)


@pytest.mark.parametrize(
    "score,expected",
    [
        (55, 55),
        ("72.9", 72),
        (150, 100),
        (-5, 0),
        ("x", None),
        (None, None),
        ([1], None),
        ({}, None),
    ]
    + [(float("inf"), None), (float("nan"), None)],
)
def test_atlas_snapshot_score_is_clamped_or_dropped(score, expected):
    import json

    raw = json.dumps({"overall_score": score}, allow_nan=True)

    assert transport._atlas_extract_ai_snapshot_fields(raw)[0] == expected


def test_openai_non_json_body_is_reported_not_raised(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("AI_MODEL", "m")

    def _bad():
        raise ValueError("Expecting value: line 1 column 1")

    response = SimpleNamespace(status_code=200, text="", json=_bad)
    monkeypatch.setattr(ai_provider, "post_json_with_retry", lambda *a, **k: response)

    assert "not valid JSON" in ai_provider._call_openai_compatible_json("hi")["error"]


def test_openai_unexpected_json_error_type_is_not_swallowed(monkeypatch):
    # The handler was narrowed to ValueError: a programming error must surface, not become an "error" value.
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("AI_MODEL", "m")

    def _bug():
        raise AttributeError("bug")

    response = SimpleNamespace(status_code=200, text="", json=_bug)
    monkeypatch.setattr(ai_provider, "post_json_with_retry", lambda *a, **k: response)

    with pytest.raises(AttributeError):
        ai_provider._call_openai_compatible_json("hi")


@pytest.fixture
def broken_database(monkeypatch):
    def _boom():
        raise RuntimeError("database is down")

    import src.database

    monkeypatch.setattr(src.database, "get_session_context", _boom)
    monkeypatch.setattr(audit, "_AUDIT_ACTOR_LOOKUP_FAILURE_REPORTED", False)
    monkeypatch.setattr(audit, "_AUDIT_DB_FAILURE_REPORTED", False)


def test_actor_lookup_failure_returns_empty_identity(broken_database):
    assert audit._resolve_actor_snapshot("alice") == {
        "actor_user_id": None,
        "actor_role": None,
        "actor_team_id": None,
    }


def test_actor_lookup_failure_is_logged_once_at_warning(broken_database, caplog):
    with caplog.at_level(logging.DEBUG, logger=audit._MODULE_LOGGER.name):
        audit._resolve_actor_snapshot("alice")
        audit._resolve_actor_snapshot("alice")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    debug = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(warnings) == 1
    assert "actor identity" in warnings[0].getMessage()
    assert len(debug) >= 2  # every failure keeps its traceback at debug


def test_empty_actor_skips_the_lookup(monkeypatch):
    import src.database

    monkeypatch.setattr(
        src.database, "get_session_context", lambda: pytest.fail("must not be called")
    )

    assert audit._resolve_actor_snapshot("   ")["actor_user_id"] is None
    assert audit._resolve_actor_snapshot(None)["actor_user_id"] is None


@pytest.mark.parametrize(
    "analysis,expected",
    [
        # Non-English warning text must not be read as "overdue" by keyword.
        (
            {"deadline_state": "overdue", "deadline_warnings": ["مهلت گذشته است"]},
            "overdue",
        ),
        ({"deadline_state": "risk", "deadline_warnings": ["خطر تاخیر"]}, "risk"),
        ({"deadline_state": "none", "deadline_warnings": ["anything"]}, None),
        ({"deadline_state": " RISK "}, "risk"),
        # Older stored analyses have no deadline_state: keep the keyword fallback.
        ({"deadline_warnings": ["KR-2 overdue"]}, "overdue"),
        ({"deadline_warnings": ["slipping"]}, "risk"),
        ({"deadline_warnings": []}, None),
        ({"deadline_state": "bogus", "deadline_warnings": ["slipping"]}, "risk"),
    ],
)
def test_atlas_snapshot_deadline_state_is_language_independent(analysis, expected):
    import json

    from src.domain.read_queries import _atlas_extract_ai_snapshot_fields

    raw = json.dumps(analysis, ensure_ascii=False)

    assert transport._atlas_extract_ai_snapshot_fields(raw)[1] == expected
    assert _atlas_extract_ai_snapshot_fields(raw)[1] == expected
