"""Tests for scripts/check_insert_contract.py (offline baseline mode only)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_insert_contract import _schema_from_baseline, check  # noqa: E402


def test_baseline_schema_parses_tracked_tables():
    schema = _schema_from_baseline()
    for table in ("user", "team", "work_log"):
        assert table in schema and schema[table], f"no columns parsed for {table}"


def test_baseline_user_columns_match_live_semantics():
    cols = _schema_from_baseline()["user"]
    # token_version must carry its DEFAULT 1 in the DDL (regression: it was
    # missing from the squashed baseline while present in the live DB).
    assert cols["token_version"] == (True, True)
    assert cols["created_at"] == (True, False)
    assert cols["role"] == (True, False)


def test_check_passes_when_map_matches_baseline():
    errors = check(_schema_from_baseline())
    assert errors == []


def test_check_flags_missing_required_column():
    from check_insert_contract import _REQUIRED_INSERT_COLUMNS

    schema = _schema_from_baseline()
    mutated = {t: dict(c) for t, c in schema.items()}
    mutated["team"]["created_at"] = (True, False)  # stays required
    # Simulate drift: a new NOT NULL no-default column absent from the map.
    mutated["team"]["locked_until"] = (True, False)
    saved = dict(_REQUIRED_INSERT_COLUMNS)
    try:
        _REQUIRED_INSERT_COLUMNS.clear()
        _REQUIRED_INSERT_COLUMNS.update(saved)
        errors = check(mutated)
        assert any("team.locked_until" in e for e in errors)
    finally:
        _REQUIRED_INSERT_COLUMNS.clear()
        _REQUIRED_INSERT_COLUMNS.update(saved)


def test_check_flags_stale_required_entry():
    from check_insert_contract import _REQUIRED_INSERT_COLUMNS

    schema = _schema_from_baseline()
    mutated = {t: dict(c) for t, c in schema.items()}
    # Simulate the column gaining a server default — map entry becomes stale.
    mutated["team"]["created_at"] = (True, True)
    saved = dict(_REQUIRED_INSERT_COLUMNS)
    try:
        _REQUIRED_INSERT_COLUMNS.clear()
        _REQUIRED_INSERT_COLUMNS.update(saved)
        errors = check(mutated)
        assert any("team.created_at" in e and "server default" in e for e in errors)
    finally:
        _REQUIRED_INSERT_COLUMNS.clear()
        _REQUIRED_INSERT_COLUMNS.update(saved)
