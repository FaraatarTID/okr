#!/usr/bin/env python3
"""Validate recorded service restart/failure-isolation evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.evidence_metadata import validate_evidence_metadata

REQUIRED_SCENARIOS = {
    "bff_unavailable_api_reachable",
    "api_unavailable_bff_reports_dependency_failure",
    "worker_unavailable_api_remains_ready",
}


def validate_failure_isolation(
    evidence: dict[str, Any], *, base_dir: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if base_dir is not None:
        errors.extend(validate_evidence_metadata(evidence))
    if evidence.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    scenarios = evidence.get("scenarios")
    if not isinstance(scenarios, list):
        return errors + ["scenarios must be a list"]
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            errors.append(f"scenarios[{index}] must be an object")
            continue
        name = scenario.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"scenarios[{index}].name is required")
            continue
        seen.add(name)
        if scenario.get("status") != "passed":
            errors.append(f"scenario {name} status must be passed")
        if not isinstance(scenario.get("observed"), str) or not scenario["observed"].strip():
            errors.append(f"scenario {name} observed result is required")
        if not isinstance(scenario.get("artifact"), str) or not scenario["artifact"].strip():
            errors.append(f"scenario {name} artifact is required")
        elif base_dir is not None:
            artifact = Path(scenario["artifact"])
            if artifact.is_absolute() or ".." in artifact.parts:
                errors.append(f"scenario {name} artifact must stay below the evidence directory")
            elif not (base_dir / artifact).is_file():
                errors.append(f"scenario {name} artifact does not exist: {artifact}")
    for missing in sorted(REQUIRED_SCENARIOS - seen):
        errors.append(f"missing required scenario {missing}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"failure-isolation evidence is unreadable: {exc}", file=sys.stderr)
        return 2
    errors = validate_failure_isolation(payload, base_dir=args.evidence.parent)
    if errors:
        print("Failure-isolation evidence is incomplete:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Failure-isolation evidence is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
