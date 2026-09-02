"""Validate a local release pair for rollback preparation without deploying it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.verify_rollback_evidence import RollbackEvidenceError, verify_rollback_manifest


class ReleasePairError(ValueError):
    """Raised when two release manifests cannot form a rollback pair."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleasePairError(f"could not read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleasePairError(f"manifest {path} must contain an object")
    return value


def verify_release_pair(
    new_manifest: dict[str, Any], old_manifest: dict[str, Any]
) -> dict[str, Any]:
    """Verify a distinct current/rollback pair without making deployment claims."""
    try:
        new_commit = new_manifest["commit_sha"]
        old_commit = old_manifest["commit_sha"]
        new_result = verify_rollback_manifest(new_manifest, new_commit)
        old_result = verify_rollback_manifest(old_manifest, old_commit)
    except (KeyError, RollbackEvidenceError) as exc:
        raise ReleasePairError(str(exc)) from exc

    if new_commit == old_commit:
        raise ReleasePairError("new and old manifests must have different commit SHAs")
    if new_result["images"] != old_result["images"]:
        raise ReleasePairError("new and old manifests must contain the same artifact set")

    return {
        "schema_version": 1,
        "status": "DRY_RUN_ONLY",
        "verified": True,
        "new_release": new_result,
        "old_release": old_result,
        "deployment_performed": False,
        "rollback_rehearsal_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-manifest", type=Path, required=True)
    parser.add_argument("--old-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        result = verify_release_pair(_load(args.new_manifest), _load(args.old_manifest))
    except ReleasePairError as exc:
        print(f"[RELEASE-PAIR] verification failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    print("[RELEASE-PAIR] distinct immutable release pair verified; no deployment performed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
