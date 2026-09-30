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
from src.services import ai_provider


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

    assert _atlas_extract_ai_snapshot_fields(raw)[1] == expected
