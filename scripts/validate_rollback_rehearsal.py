#!/usr/bin/env python3
"""Validate recorded BFF/API rollback rehearsal evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.evidence_metadata import validate_evidence_metadata


def validate_rollback_rehearsal(
    evidence: dict[str, Any], *, base_dir: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if base_dir is not None:
        errors.extend(validate_evidence_metadata(evidence))
    if evidence.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("last_known_good_release", "candidate_release"):
        if not isinstance(evidence.get(field), str) or not evidence[field].strip():
            errors.append(f"{field} is required")
    if evidence.get("status") != "passed":
        errors.append("status must be passed")
    duration = evidence.get("restoration_duration_seconds")
    if not isinstance(duration, (int, float)) or duration < 0:
        errors.append("restoration_duration_seconds must be non-negative")
    if evidence.get("data_integrity") != "verified":
        errors.append("data_integrity must be verified")
    artifact = evidence.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        errors.append("artifact is required")
    elif base_dir is not None:
        path = Path(artifact)
        if path.is_absolute() or ".." in path.parts:
            errors.append("artifact must stay below the evidence directory")
        elif not (base_dir / path).is_file():
            errors.append(f"artifact does not exist: {path}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"rollback evidence is unreadable: {exc}", file=sys.stderr)
        return 2
    errors = validate_rollback_rehearsal(payload, base_dir=args.evidence.parent)
    if errors:
        print("Rollback evidence is incomplete:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Rollback evidence is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
