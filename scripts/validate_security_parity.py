#!/usr/bin/env python3
"""Validate recorded security-parity evidence for a topology review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.evidence_metadata import validate_evidence_metadata

REQUIRED_CONTROLS = {
    "session_cookie_protection",
    "csrf_and_origin_controls",
    "actor_binding",
    "request_signing",
    "route_allowlisting",
    "rate_limiting",
}


def validate_security_parity(
    evidence: dict[str, Any], *, base_dir: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if base_dir is not None:
        errors.extend(validate_evidence_metadata(evidence))
    if evidence.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    controls = evidence.get("controls")
    if not isinstance(controls, list):
        return errors + ["controls must be a list"]
    seen: set[str] = set()
    for index, control in enumerate(controls):
        if not isinstance(control, dict):
            errors.append(f"controls[{index}] must be an object")
            continue
        name = control.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"controls[{index}].name is required")
            continue
        seen.add(name)
        if control.get("status") != "passed":
            errors.append(f"control {name} status must be passed")
        if not isinstance(control.get("observed"), str) or not control["observed"].strip():
            errors.append(f"control {name} observed result is required")
        artifact = control.get("artifact")
        if not isinstance(artifact, str) or not artifact.strip():
            errors.append(f"control {name} artifact is required")
        elif base_dir is not None:
            path = Path(artifact)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"control {name} artifact must stay below the evidence directory")
            elif not (base_dir / path).is_file():
                errors.append(f"control {name} artifact does not exist: {path}")
    for missing in sorted(REQUIRED_CONTROLS - seen):
        errors.append(f"missing required control {missing}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"security-parity evidence is unreadable: {exc}", file=sys.stderr)
        return 2
    errors = validate_security_parity(payload, base_dir=args.evidence.parent)
    if errors:
        print("Security-parity evidence is incomplete:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Security-parity evidence is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
