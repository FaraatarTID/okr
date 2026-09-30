"""Shared constants for required INSERT columns used by INSERT contract checks."""

from __future__ import annotations

# Columns that are NOT NULL with no DB server default in the live schema.
# An INSERT missing any of these will fail with 23502 at runtime.
# (token_version has a DB default of 1, so it is not required.)
REQUIRED_INSERT_COLUMNS: dict[str, set[str]] = {
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
