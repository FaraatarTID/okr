#!/usr/bin/env python3
"""Validate Alembic migration graph integrity.

Gate checks implemented:
1. Every revision file exposes a parseable revision identifier.
2. All down-revision references resolve to existing revisions.
3. Migration graph is a single linear chain (single root and single head).
4. No merge revisions (multiple down-revisions) that branch history.
5. No cycles in the down-revision chain.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "alembic" / "versions"


class _RevisionRecord:
    def __init__(self, revision: str, down_revisions: tuple[str, ...], path: Path) -> None:
        self.revision = revision
        self.down_revisions = down_revisions
        self.path = path


def _literal_value(node: ast.AST) -> object | None:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        values = [_literal_value(item) for item in node.elts]
        if all(item is not None and isinstance(item, str) for item in values):
            return tuple(item for item in values if isinstance(item, str))
        if all(item is None for item in values):
            return ()
        return None
    if isinstance(node, ast.Tuple):
        values = [_literal_value(item) for item in node.elts]
        if all(item is not None and isinstance(item, str) for item in values):
            return tuple(item for item in values if isinstance(item, str))
        if all(item is None for item in values):
            return ()
        return None
    if isinstance(node, ast.Name) and node.id == "None":
        return None
    return None


def _parse_migration_file(path: Path) -> _RevisionRecord | None:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{path}: cannot parse as Python source: {exc}") from exc

    revision = None
    down_revision: tuple[str, ...] = ()
    for node in tree.body:
        targets: list[ast.Name] = []
        expr: ast.AST | None = None
        if isinstance(node, ast.Assign):
            targets = [target for target in node.targets if isinstance(target, ast.Name)]
            expr = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                targets = [node.target]
            expr = node.value
        if not targets or expr is None:
            continue

        for target in targets:
            name = target.id
            if name == "revision":
                value = _literal_value(expr)
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeError(
                        f"{path}: invalid revision value {value!r}, expected non-empty string."
                    )
                revision = value.strip()
            elif name == "down_revision":
                value = _literal_value(expr)
                if value is None:
                    down_revision = ()
                elif isinstance(value, tuple) and all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    down_revision = tuple(item.strip() for item in value)
                elif isinstance(value, str) and value.strip():
                    down_revision = (value.strip(),)
                else:
                    raise RuntimeError(
                        f"{path}: invalid down_revision value {value!r}; "
                        "expected None, string, or tuple/list of strings."
                    )

    if revision is None:
        return None
    return _RevisionRecord(revision=revision, down_revisions=down_revision, path=path)


def _collect_revisions(versions_dir: Path) -> list[_RevisionRecord]:
    records: list[_RevisionRecord] = []
    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__pycache__":
            continue
        record = _parse_migration_file(path)
        if record is not None:
            records.append(record)
    return records


def _validate_linear_chain(
    records: list[_RevisionRecord],
    *,
    require_baseline: bool,
    require_single_head: bool,
) -> list[str]:
    if not records:
        return ["No migration files found under alembic/versions."]

    errors: list[str] = []
    by_revision: dict[str, _RevisionRecord] = {}
    for rec in records:
        if rec.revision in by_revision:
            errors.append(
                f"Duplicate revision id '{rec.revision}' in {rec.path.name} "
                f"and {by_revision[rec.revision].path.name}."
            )
        by_revision[rec.revision] = rec

    if errors:
        return errors

    revisions = list(by_revision.values())
    referenced = [parent for rec in revisions for parent in rec.down_revisions]
    missing = [parent for parent in referenced if parent not in by_revision]
    if missing:
        for parent in sorted(set(missing)):
            errors.append(
                f"Down-revision reference '{parent}' does not exist in alembic/versions."
            )
        return errors

    merge_candidates = [rec.revision for rec in revisions if len(rec.down_revisions) > 1]
    if merge_candidates:
        merge_items = ", ".join(merge_candidates)
        errors.append(
            f"Merge/branch revisions found (multiple parents): {merge_items}. "
            "Migrations are expected to be linear for this readiness model."
        )

    roots = [rec for rec in revisions if not rec.down_revisions]
    if not roots:
        errors.append("No migration has down_revision=None; cannot determine chain root.")
        return errors
    if len(roots) > 1:
        root_ids = ", ".join(sorted(rec.revision for rec in roots))
        errors.append(f"Multiple migration roots found: {root_ids}.")
        return errors

    if require_baseline and not roots[0].path.name.startswith("baseline_"):
        errors.append(
            f"Root migration '{roots[0].revision}' is '{roots[0].path.name}' and is "
            "not baseline-prefixed as expected for this policy."
        )

    referenced_count = Counter(referenced)
    heads = [rec for rec in revisions if referenced_count[rec.revision] == 0]
    if not heads:
        errors.append("No head revision could be determined from the migration graph.")
        return errors
    if require_single_head and len(heads) > 1:
        head_ids = ", ".join(sorted(rec.revision for rec in heads))
        errors.append(f"Multiple heads found: {head_ids}.")
        return errors

    # Reachability/cycle checks by walking from each head to root.
    parent_index = {rec.revision: rec.down_revisions[0] if rec.down_revisions else None for rec in revisions}
    head_revisions = [rec.revision for rec in heads]
    for head in head_revisions:
        chain_seen: set[str] = set()
        cursor: str | None = head
        while cursor is not None:
            if cursor in chain_seen:
                errors.append(
                    f"Cycle detected while walking migration chain from '{head}'."
                )
                return errors
            chain_seen.add(cursor)
            cursor = parent_index.get(cursor)

        # If not all revisions are reachable from the selected head(s), we have
        # a disconnected branch in the history. In practice this should only
        # happen if the history is malformed.
        if not require_single_head and len(head_revisions) > 1:
            continue

    if require_single_head:
        all_revisions = {rec.revision for rec in revisions}
        seen = chain_seen
        if heads and seen != all_revisions:
            missing_revisions = sorted(all_revisions - seen)
            if missing_revisions:
                errors.append(
                    "Disconnected migration history detected: "
                    f"unreachable revision(s): {', '.join(missing_revisions)}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--versions-dir",
        type=Path,
        default=VERSIONS_DIR,
        help="Directory containing Alembic revision scripts.",
    )
    parser.add_argument(
        "--require-baseline",
        action="store_true",
        help="Fail if the single root revision is not baseline-prefixed.",
    )
    parser.add_argument(
        "--allow-multiple-heads",
        action="store_true",
        help="Allow temporary multi-head states (legacy branch tolerance).",
    )
    args = parser.parse_args()

    versions_dir = args.versions_dir.resolve()
    records = _collect_revisions(versions_dir)
    errors = _validate_linear_chain(
        records,
        require_baseline=bool(args.require_baseline),
        require_single_head=not bool(args.allow_multiple_heads),
    )

    print(f"Checking migration graph in: {versions_dir.as_posix()}")
    print(f"Found {len(records)} revision scripts.")
    if errors:
        print(f"Migration lint FAILED ({len(errors)} issue(s)): ")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.allow_multiple_heads:
        print("Migration lint passed (branching allowed by explicit flag).")
    else:
        print("Migration lint passed: single-root, single-head, acyclic linear graph.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
