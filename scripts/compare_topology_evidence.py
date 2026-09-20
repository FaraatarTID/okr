#!/usr/bin/env python3
"""Compare two sanitized ``slo_probe.py --output`` evidence artifacts.

The report is deliberately decision support, not an automatic recommendation.
It makes the latency and reliability trade-offs between two topologies explicit
while leaving security and rollback evidence for human review.
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.evidence_metadata import validate_evidence_metadata


class EvidenceError(ValueError):
    """Raised when an SLO evidence artifact is incomplete or malformed."""


def compare_resources(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    resource_map: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Compare numeric CPU snapshots when Docker emitted parseable percentages."""
    baseline_items = {item["container"]: item for item in baseline.get("services", [])}
    candidate_items = {
        item["container"]: item for item in candidate.get("services", [])
    }
    if resource_map is None and set(baseline_items) != set(candidate_items):
        raise EvidenceError("resource snapshots must contain the same containers")
    if resource_map is not None:
        pairs = []
        for logical, names in resource_map.items():
            if not isinstance(logical, str) or not isinstance(names, dict):
                raise EvidenceError(
                    "resource map entries must be logical names and objects"
                )
            baseline_name = names.get("baseline")
            candidate_name = names.get("candidate")
            if not isinstance(baseline_name, str) or not isinstance(
                candidate_name, str
            ):
                raise EvidenceError(f"resource map entry is incomplete for {logical}")
            pairs.append((logical, baseline_name, candidate_name))
        pairs.sort()
    else:
        pairs = [
            (container, container, container) for container in sorted(baseline_items)
        ]
    comparisons = []
    for logical, baseline_container, candidate_container in pairs:
        if (
            baseline_container not in baseline_items
            or candidate_container not in candidate_items
        ):
            raise EvidenceError(
                f"resource map references an unknown container for {logical}"
            )
        before = baseline_items[baseline_container]
        after = candidate_items[candidate_container]
        try:
            baseline_cpu = float(str(before["cpu_percent"]).rstrip("%"))
            candidate_cpu = float(str(after["cpu_percent"]).rstrip("%"))
        except (KeyError, TypeError, ValueError) as exc:
            raise EvidenceError(f"resource CPU value is invalid for {logical}") from exc
        comparisons.append(
            {
                "container": logical,
                "baseline_cpu_percent": baseline_cpu,
                "candidate_cpu_percent": candidate_cpu,
                "cpu_delta_percent": round(candidate_cpu - baseline_cpu, 3),
                "baseline_memory": before.get("memory"),
                "candidate_memory": after.get("memory"),
                "baseline_sample_count": before.get("sample_count", 1),
                "candidate_sample_count": after.get("sample_count", 1),
            }
        )
    return comparisons


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read evidence {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise EvidenceError(f"{path} must contain schema_version 1")
    metadata_errors = validate_evidence_metadata(payload)
    if metadata_errors:
        raise EvidenceError(f"{path} metadata invalid: {', '.join(metadata_errors)}")
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise EvidenceError(f"{path} must contain a non-empty results list")
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise EvidenceError(f"{path}: results[{index}] must be an object")
        if not isinstance(item.get("slo"), str):
            raise EvidenceError(f"{path}: results[{index}].slo is required")
        if not isinstance(item.get("measured_s"), (int, float)):
            raise EvidenceError(f"{path}: results[{index}].measured_s is required")
        if not isinstance(item.get("pass"), bool):
            raise EvidenceError(f"{path}: results[{index}].pass is required")
    return payload


def compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    resource_comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if baseline.get("release_id") != candidate.get("release_id"):
        raise EvidenceError("topologies must use evidence from the same release_id")
    baseline_items = {item["slo"]: item for item in baseline["results"]}
    candidate_items = {item["slo"]: item for item in candidate["results"]}
    if set(baseline_items) != set(candidate_items):
        missing = sorted(set(baseline_items) - set(candidate_items))
        extra = sorted(set(candidate_items) - set(baseline_items))
        raise EvidenceError(
            f"topologies must measure the same SLOs; missing={missing}, extra={extra}"
        )

    comparisons = []
    for slo in sorted(baseline_items):
        before = baseline_items[slo]
        after = candidate_items[slo]
        baseline_seconds = float(before["measured_s"])
        candidate_seconds = float(after["measured_s"])
        comparisons.append(
            {
                "slo": slo,
                "baseline_s": round(baseline_seconds, 3),
                "candidate_s": round(candidate_seconds, 3),
                "delta_s": round(candidate_seconds - baseline_seconds, 3),
                "relative_change_pct": round(
                    ((candidate_seconds - baseline_seconds) / baseline_seconds) * 100, 2
                )
                if baseline_seconds
                else None,
                "baseline_pass": before["pass"],
                "candidate_pass": after["pass"],
            }
        )

    return {
        "schema_version": 1,
        "release_id": baseline.get("release_id")
        or candidate.get("release_id")
        or "local",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "operator": os.getenv("GITHUB_ACTOR", "local"),
        "topology": "comparison",
        "baseline_url": baseline.get("base_url"),
        "candidate_url": candidate.get("base_url"),
        "baseline_passed": sum(1 for item in baseline["results"] if item["pass"]),
        "candidate_passed": sum(1 for item in candidate["results"] if item["pass"]),
        "comparisons": comparisons,
        "resource_comparisons": resource_comparisons or [],
        "decision": "human_review_required",
        "required_follow_up": [
            "compare security parity",
            "rehearse independent restart and rollback",
            "confirm resource and failure-isolation evidence",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--baseline-resources", type=Path, default=None)
    parser.add_argument("--candidate-resources", type=Path, default=None)
    parser.add_argument("--resource-map", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        resource_comparisons = None
        if (args.baseline_resources is None) != (args.candidate_resources is None):
            raise EvidenceError(
                "both resource snapshots are required when comparing resources"
            )
        if args.resource_map is not None and args.baseline_resources is None:
            raise EvidenceError("--resource-map requires resource snapshots")
        if args.baseline_resources is not None and args.candidate_resources is not None:
            resource_map = None
            if args.resource_map is not None:
                resource_map = json.loads(args.resource_map.read_text(encoding="utf-8"))
                if not isinstance(resource_map, dict):
                    raise EvidenceError("--resource-map must contain a JSON object")
            baseline_resources = json.loads(
                args.baseline_resources.read_text(encoding="utf-8")
            )
            candidate_resources = json.loads(
                args.candidate_resources.read_text(encoding="utf-8")
            )
            if not isinstance(baseline_resources, dict) or not isinstance(
                candidate_resources, dict
            ):
                raise EvidenceError("resource snapshots must contain JSON objects")
            metadata_errors = validate_evidence_metadata(
                baseline_resources
            ) + validate_evidence_metadata(candidate_resources)
            if metadata_errors:
                raise EvidenceError(
                    f"resource snapshot metadata invalid: {', '.join(metadata_errors)}"
                )
            if baseline_resources.get("release_id") != candidate_resources.get(
                "release_id"
            ):
                raise EvidenceError("resource snapshots must use the same release_id")
            resource_comparisons = compare_resources(
                baseline_resources,
                candidate_resources,
                resource_map=resource_map,
            )
        report = compare(
            _load(args.baseline),
            _load(args.candidate),
            resource_comparisons=resource_comparisons,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except EvidenceError as exc:
        print(f"topology evidence comparison failed: {exc}", file=sys.stderr)
        return 2
    print(f"Topology comparison written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
