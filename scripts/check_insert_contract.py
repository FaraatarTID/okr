#!/usr/bin/env python3
"""Contract check: API-mode INSERT payloads vs. live DB schema.

Verifies that every column listed in ``_REQUIRED_INSERT_COLUMNS`` (the columns
API-mode create helpers must send explicitly) is still NOT NULL without a
server default in the actual database, and vice versa: finds NOT NULL /
no-default columns that are missing from the map — i.e. inserts that would
fail with PostgREST error 23502 at runtime.

Data sources, in order of preference:
1. Live DB via ``OKR_DATABASE_URL`` (default; authoritative).
2. ``--from-baseline``: parse the squashed Alembic baseline DDL instead, so
   the check also runs offline / in CI without DB credentials.

Exit codes: 0 = pass, 1 = drift detected or error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.required_insert_columns import REQUIRED_INSERT_COLUMNS  # noqa: E402

BASELINE_PATH = PROJECT_ROOT / "alembic" / "versions" / "baseline_2026_08_26_schema.py"

# Backward-compatible export expected by tests and existing callers.
_REQUIRED_INSERT_COLUMNS = REQUIRED_INSERT_COLUMNS

# Tables the API-mode helpers insert into and that we track in the contract.
TRACKED_TABLES = sorted(_REQUIRED_INSERT_COLUMNS.keys())


def _schema_from_live_db() -> dict[str, dict[str, tuple[bool, bool]]]:
    """Return {table: {column: (not_null, has_default)}} from the live DB."""
    import sqlalchemy
    from sqlalchemy import text

    url = os.environ.get("OKR_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("OKR_DATABASE_URL is not set; cannot inspect live schema.")
    engine = sqlalchemy.create_engine(url)
    result: dict[str, dict[str, tuple[bool, bool]]] = {}
    with engine.connect() as conn:
        for table in TRACKED_TABLES:
            rows = conn.execute(
                text(
                    "select column_name, is_nullable, column_default "
                    "from information_schema.columns "
                    "where table_schema = 'public' and table_name = :t"
                ),
                {"t": table},
            ).fetchall()
            if not rows:
                raise RuntimeError(f"Table '{table}' not found in live schema.")
            cols: dict[str, tuple[bool, bool]] = {}
            for name, nullable, default in rows:
                cols[str(name)] = (
                    str(nullable).upper() == "NO",
                    default is not None,
                )
            result[table] = cols
    return result


def _split_top_level(line: str) -> list[str]:
    """Split a DDL column line on commas not nested in parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in line:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _schema_from_baseline() -> dict[str, dict[str, tuple[bool, bool]]]:
    """Parse CREATE TABLE DDL from the squashed baseline migration."""
    ddl = BASELINE_PATH.read_text(encoding="utf-8")
    result: dict[str, dict[str, tuple[bool, bool]]] = {}
    for table in TRACKED_TABLES:
        quoted = f'"{table}"' if table == "user" else table
        match = re.search(
            rf"CREATE TABLE {re.escape(quoted)} \((.*?)\n\)\n",
            ddl,
            re.DOTALL,
        )
        if not match:
            raise RuntimeError(f"CREATE TABLE for '{table}' not found in baseline.")
        body = match.group(1)
        cols: dict[str, tuple[bool, bool]] = {}
        for part in _split_top_level(body):
            upper = part.upper()
            # Skip constraint clauses.
            if upper.startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT")):
                continue
            m = re.match(r"(\w+|\S+)\s+(.+)", part, re.DOTALL)
            if not m:
                continue
            name = m.group(1).strip('"')
            rest = m.group(2).upper()
            not_null = "NOT NULL" in rest
            has_default = "DEFAULT" in rest
            # SERIAL implies an implicit sequence default.
            if "SERIAL" in rest:
                has_default = True
            cols[name] = (not_null, has_default)
        result[table] = cols
    return result


def check(schema: dict[str, dict[str, tuple[bool, bool]]]) -> list[str]:
    """Cross-check the required-columns map against the schema."""
    errors: list[str] = []
    for table in TRACKED_TABLES:
        cols = schema.get(table, {})
        required = _REQUIRED_INSERT_COLUMNS.get(table, set())

        for col in sorted(required):
            info = cols.get(col)
            if info is None:
                errors.append(
                    f"{table}.{col}: listed as required-insert but does not exist in schema."
                )
                continue
            not_null, has_default = info
            if not not_null:
                errors.append(
                    f"{table}.{col}: listed as required-insert but is nullable — "
                    f"remove it from _REQUIRED_INSERT_COLUMNS."
                )
            elif has_default:
                errors.append(
                    f"{table}.{col}: listed as required-insert but has a server "
                    f"default — remove it from _REQUIRED_INSERT_COLUMNS."
                )

        # The important direction: find runtime 23502 landmines missing from the map.
        for name, (not_null, has_default) in sorted(cols.items()):
            if not_null and not has_default and name not in required:
                errors.append(
                    f"{table}.{name}: NOT NULL with no server default but MISSING "
                    f"from _REQUIRED_INSERT_COLUMNS — API-mode inserts omitting it "
                    f"will fail with 23502."
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-baseline",
        action="store_true",
        help="Check against the squashed baseline migration DDL instead of the live DB.",
    )
    args = parser.parse_args()

    try:
        if args.from_baseline:
            source = f"baseline migration ({BASELINE_PATH.name})"
            schema = _schema_from_baseline()
        else:
            source = "live database (OKR_DATABASE_URL)"
            schema = _schema_from_live_db()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        return 1

    errors = check(schema)

    print(f"Schema contract source: {source}")
    print(f"Tracked tables: {', '.join(TRACKED_TABLES)}")
    if errors:
        print(f"\nSchema contract check FAILED ({len(errors)} issue(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Schema contract check passed: required-insert maps match the schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
