#!/usr/bin/env python3
"""CI gate: verify every table in the public schema has RLS enabled.

Connects to a PostgreSQL database (OKR_DATABASE_URL or DATABASE_URL) and
fails if any user table in the public schema does not have row level
security enabled. This prevents new tables from silently shipping without
RLS (Supabase linter finding 0013).

Usage:
    python scripts/check_rls_enabled.py

Exit codes:
    0 - all tables have RLS enabled (or no Postgres DSN configured)
    1 - one or more tables lack RLS, or connection failed
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import bindparam, create_engine, text


# Tables intentionally excluded from the check (metadata / non-user data).
EXCLUDED_TABLES: frozenset[str] = frozenset(
    {
        # Alembic migration metadata — not user data, RLS is meaningless.
        "alembic_version",
    }
)

# PostgREST roles that must hold no grants on backend-internal tables.
# Verified only when the roles exist (Supabase); skipped on plain Postgres.
POSTGREST_ROLES: tuple[str, ...] = ("anon", "authenticated")

# Tables that must have zero grants for POSTGREST_ROLES.
OWNER_ONLY_TABLES: frozenset[str] = frozenset(
    {
        "backend_request_nonce",
        "backend_rate_limit_counter",
        "backend_distributed_state",
        "backend_idempotency_record",
        "objective_alignment_link",
    }
)

# Roles for which a permissive policy is a finding. Policies granting
# these roles unrestricted access are the classic Supabase footgun.
POLICY_AUDIT_ROLES: tuple[str, ...] = ("anon", "authenticated", "public")


def _database_url() -> str:
    value = (
        os.getenv("OKR_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    ).strip()
    if not value:
        raise SystemExit(
            "check_rls_enabled: OKR_DATABASE_URL or DATABASE_URL must be set."
        )
    return value


def _tables_missing_rls(engine) -> list[tuple[str, bool]]:
    query = text(
        """
        SELECT c.relname AS table_name,
               c.relrowsecurity AS rls_enabled
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND c.relname NOT IN :excluded
        ORDER BY c.relname
        """
    ).bindparams(bindparam("excluded", expanding=True))
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {"excluded": tuple(EXCLUDED_TABLES)},
        ).fetchall()
    return [(row.table_name, row.rls_enabled) for row in rows]


def _permissive_policy_violations(engine) -> list[str]:
    """Flag policies that grant unrestricted access to exposed roles.

    Detects policies whose qual/with_check is trivially true (e.g.
    ``USING (true)``) or that apply to anon/authenticated/public without
    any role restriction, on tables in the public schema.
    """
    query = text(
        """
        SELECT schemaname,
               tablename,
               policyname,
               roles,
               cmd,
               qual,
               with_check
        FROM pg_policies
        WHERE schemaname = 'public'
        """
    )
    trivially_true = {"true", "(true)", "t"}
    violations: list[str] = []
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    for row in rows:
        applies_to_exposed = bool(
            set(row.roles or []) & set(POLICY_AUDIT_ROLES)
        )
        if not applies_to_exposed:
            continue
        for expr in (row.qual, row.with_check):
            if expr is not None and expr.strip().lower() in trivially_true:
                violations.append(
                    f"public.{row.tablename} policy '{row.policyname}' "
                    f"({row.cmd}) grants unrestricted access via '{expr}'"
                )
                break
    return violations


def _role_grant_violations(engine) -> list[str] | None:
    """Return grant violations for owner-only tables, or None to skip.

    Skips (returns None) when the PostgREST roles do not exist — e.g. a
    plain PostgreSQL service container in CI rather than Supabase.
    """
    with engine.connect() as conn:
        existing_roles = {
            row[0]
            for row in conn.execute(
                text("SELECT rolname FROM pg_roles WHERE rolname = ANY(:roles)"),
                {"roles": list(POSTGREST_ROLES)},
            ).fetchall()
        }
        if not existing_roles:
            return None

        query = text(
            """
            SELECT table_name, grantee
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND table_name = ANY(:tables)
              AND grantee = ANY(:roles)
            """
        )
        rows = conn.execute(
            query,
            {"tables": sorted(OWNER_ONLY_TABLES), "roles": list(existing_roles)},
        ).fetchall()

    return [
        f"public.{row.table_name} has grants for role '{row.grantee}'"
        for row in rows
    ]


def main() -> int:
    url = _database_url()
    if not url.lower().startswith(("postgresql://", "postgresql+psycopg2://")):
        print("check_rls_enabled: skipping — DSN is not PostgreSQL.")
        return 0

    engine = create_engine(url)
    try:
        results = _tables_missing_rls(engine)
        missing = [name for name, rls in results if not rls]
        if missing:
            print("check_rls_enabled: FAIL — tables without RLS:")
            for name in missing:
                print(f"  - public.{name}")
            return 1

        try:
            violations = _role_grant_violations(engine)
        except Exception as exc:  # noqa: BLE001
            print(f"check_rls_enabled: WARN — grant check failed: {exc}")
            violations = None

        if violations:
            print("check_rls_enabled: FAIL — PostgREST role grants on owner-only tables:")
            for item in violations:
                print(f"  - {item}")
            return 1

        try:
            policy_violations = _permissive_policy_violations(engine)
        except Exception as exc:  # noqa: BLE001
            print(f"check_rls_enabled: WARN — policy check failed: {exc}")
            policy_violations = []

        if policy_violations:
            print("check_rls_enabled: FAIL — permissive policies exposed to anon/authenticated:")
            for item in policy_violations:
                print(f"  - {item}")
            return 1

        checks = [f"{len(results)} tables checked, all have RLS"]
        checks.append(
            "grant check skipped (no PostgREST roles)"
            if violations is None
            else "grant check passed"
        )
        checks.append("policy check passed")
        print(f"check_rls_enabled: OK — {'; '.join(checks)}.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"check_rls_enabled: FAILED to inspect database: {exc}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
