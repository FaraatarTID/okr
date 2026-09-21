#!/usr/bin/env python3
"""Enforce metadata and safety policy for Alembic revisions.

Every revision must expose a literal ``MIGRATION_METADATA`` mapping.  This
checker is deliberately AST-based: reviewing a revision must not execute it.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "alembic" / "versions"
EXCEPTIONS_DIR = ROOT_DIR / "docs" / "migration-exceptions"
REQUIRED_BOOLEAN_FIELDS = (
    "additive",
    "backfill",
    "contract",
    "destructive",
    "locking_risk",
    "reversible",
    "compatible_with_previous_release",
    "maintenance_window_only",
)


@dataclass(frozen=True)
class Revision:
    revision: str
    down_revisions: tuple[str, ...]
    metadata: dict[str, Any] | None
    path: Path


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _parse(path: Path) -> Revision | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise RuntimeError(f"{path}: cannot parse Python source: {exc}") from exc
    revision = None
    down_revisions: tuple[str, ...] = ()
    metadata = None
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "revision":
                candidate = _literal(value)
                if isinstance(candidate, str) and candidate.strip():
                    revision = candidate.strip()
            elif target.id == "down_revision":
                candidate = _literal(value)
                if isinstance(candidate, str):
                    down_revisions = (candidate,)
                elif isinstance(candidate, (tuple, list)) and all(
                    isinstance(item, str) for item in candidate
                ):
                    down_revisions = tuple(candidate)
            elif target.id == "MIGRATION_METADATA":
                candidate = _literal(value)
                metadata = candidate if isinstance(candidate, dict) else None
    return Revision(revision, down_revisions, metadata, path) if revision else None


def _approved_exception(value: object, exceptions_dir: Path) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    record = exceptions_dir / value
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("status") == "approved"
        and bool(payload.get("approved_by"))
        and bool(payload.get("maintenance_window"))
    )


def validate(
    versions_dir: Path,
    exceptions_dir: Path,
    *,
    selected_revision: str | None = None,
    production_fleet: bool = False,
) -> list[str]:
    revisions = [
        record for path in sorted(versions_dir.glob("*.py")) if (record := _parse(path))
    ]
    errors: list[str] = []
    selected: list[Revision] = []
    head_ids = {
        record.revision
        for record in revisions
        if record.revision
        not in {parent for item in revisions for parent in item.down_revisions}
    }
    for record in revisions:
        if selected_revision == record.revision or (
            selected_revision == "head" and record.revision in head_ids
        ):
            selected.append(record)
        metadata = record.metadata
        label = record.path.name
        if metadata is None:
            errors.append(f"{label}: missing literal MIGRATION_METADATA mapping.")
            continue
        for field in REQUIRED_BOOLEAN_FIELDS:
            if not isinstance(metadata.get(field), bool):
                errors.append(f"{label}: metadata '{field}' must be boolean.")
        if any(
            not isinstance(metadata.get(field), bool)
            for field in REQUIRED_BOOLEAN_FIELDS
        ):
            continue
        types = sum(
            bool(metadata[name]) for name in ("additive", "backfill", "contract")
        )
        if types != 1:
            errors.append(
                f"{label}: exactly one of additive, backfill, and contract must be true."
            )
        if metadata["destructive"] and not metadata["contract"]:
            errors.append(f"{label}: destructive revisions must be contract revisions.")
        if metadata["destructive"] and metadata["compatible_with_previous_release"]:
            errors.append(
                f"{label}: destructive revisions cannot claim compatibility with the previous application release."
            )
        if metadata["locking_risk"] and not metadata["maintenance_window_only"]:
            errors.append(
                f"{label}: locking-risk operations require maintenance_window_only=true."
            )
        needs_exception = (
            metadata["destructive"]
            or metadata["locking_risk"]
            or metadata["maintenance_window_only"]
        )
        if needs_exception and not _approved_exception(
            metadata.get("exception_record"), exceptions_dir
        ):
            errors.append(
                f"{label}: unsafe revision requires an approved exception_record with a maintenance window."
            )
        if not needs_exception and metadata.get("exception_record") not in (None, ""):
            errors.append(
                f"{label}: exception_record is allowed only for an unsafe or maintenance-window revision."
            )
    if selected_revision and selected_revision != "head" and not selected:
        errors.append(f"Selected revision '{selected_revision}' was not found.")
    if production_fleet:
        for record in selected:
            if record.metadata is None:
                errors.append(
                    f"{record.path.name}: production fleet rollout requires migration metadata."
                )
            elif record.metadata.get("maintenance_window_only"):
                errors.append(
                    f"{record.path.name}: maintenance-window-only revision cannot be run in a production fleet rollout."
                )
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions-dir", type=Path, default=VERSIONS_DIR)
    parser.add_argument("--exceptions-dir", type=Path, default=EXCEPTIONS_DIR)
    parser.add_argument("--selected-revision", help="Revision to authorize, or 'head'.")
    parser.add_argument(
        "--production-fleet",
        action="store_true",
        help="Reject maintenance-window-only selected revisions.",
    )
    args = parser.parse_args(argv)
    errors = validate(
        args.versions_dir.resolve(),
        args.exceptions_dir.resolve(),
        selected_revision=args.selected_revision,
        production_fleet=args.production_fleet,
    )
    print(f"Checking migration safety in: {args.versions_dir}")
    if errors:
        print(f"Migration safety FAILED ({len(errors)} issue(s)):")
        print(*(f"- {error}" for error in errors), sep="\n")
        return 1
    print("Migration safety passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
