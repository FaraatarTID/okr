#!/usr/bin/env python3
"""Validate the evidence checklist required for a BFF topology decision."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.validate_failure_isolation import validate_failure_isolation
from scripts.validate_rollback_rehearsal import validate_rollback_rehearsal
from scripts.validate_security_parity import validate_security_parity
from scripts.evidence_metadata import validate_evidence_metadata

REQUIRED_CATEGORIES = (
    "security_parity",
    "failure_isolation",
    "resource_overhead",
    "rollback_rehearsal",
)


def validate_review(review: dict[str, Any], *, base_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if base_dir is not None:
        errors.extend(validate_evidence_metadata(review))
    if review.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    decision = review.get("decision")
    if decision not in {"retain_bff", "simplify_topology"}:
        errors.append("decision must be retain_bff or simplify_topology")
    evidence = review.get("evidence")
    if not isinstance(evidence, dict):
        return errors + ["evidence must be an object"]
    for category in REQUIRED_CATEGORIES:
        item = evidence.get(category)
        if not isinstance(item, dict):
            errors.append(f"evidence.{category} must be an object")
            continue
        if item.get("status") != "passed":
            errors.append(f"evidence.{category}.status must be passed")
        if not isinstance(item.get("artifact"), str) or not item["artifact"].strip():
            errors.append(f"evidence.{category}.artifact is required")
        elif base_dir is not None:
            artifact = Path(item["artifact"])
            if artifact.is_absolute() or ".." in artifact.parts:
                errors.append(f"evidence.{category}.artifact must stay below the review directory")
            else:
                artifact_path = base_dir / artifact
                if not artifact_path.is_file():
                    errors.append(f"evidence.{category}.artifact does not exist: {artifact}")
                else:
                    try:
                        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"evidence.{category}.artifact is unreadable: {exc}")
                    else:
                        if not isinstance(artifact_payload, dict):
                            errors.append(f"evidence.{category}.artifact must contain a JSON object")
                        elif artifact_payload.get("release_id") != review.get("release_id"):
                            errors.append(f"evidence.{category}.artifact release_id must match the review")
                        elif category == "security_parity":
                            errors.extend(validate_security_parity(artifact_payload, base_dir=base_dir))
                        elif category == "failure_isolation":
                            errors.extend(validate_failure_isolation(artifact_payload, base_dir=base_dir))
                        elif category == "rollback_rehearsal":
                            errors.extend(validate_rollback_rehearsal(artifact_payload, base_dir=base_dir))
                        elif category == "resource_overhead":
                            errors.extend(validate_evidence_metadata(artifact_payload))
                            comparisons = artifact_payload.get("resource_comparisons")
                            if not isinstance(comparisons, list) or not comparisons:
                                errors.append("resource_overhead artifact must contain resource_comparisons")
                            else:
                                for index, comparison in enumerate(comparisons):
                                    if not isinstance(comparison, dict):
                                        errors.append(f"resource_comparisons[{index}] must be an object")
                                        continue
                                    if not isinstance(comparison.get("container"), str) or not comparison["container"].strip():
                                        errors.append(f"resource_comparisons[{index}].container is required")
                                    for field in ("baseline_cpu_percent", "candidate_cpu_percent", "cpu_delta_percent"):
                                        if not isinstance(comparison.get(field), (int, float)):
                                            errors.append(f"resource_comparisons[{index}].{field} must be numeric")
                                    for field in ("baseline_sample_count", "candidate_sample_count"):
                                        if not isinstance(comparison.get(field), int) or comparison[field] < 1:
                                            errors.append(f"resource_comparisons[{index}].{field} must be positive")
        if not isinstance(item.get("summary"), str) or not item["summary"].strip():
            errors.append(f"evidence.{category}.summary is required")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    args = parser.parse_args(argv)
    try:
        review = json.loads(args.review.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"topology review is unreadable: {exc}", file=sys.stderr)
        return 2
    errors = validate_review(review, base_dir=args.review.parent)
    if errors:
        print("Topology review is incomplete:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Topology review is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
