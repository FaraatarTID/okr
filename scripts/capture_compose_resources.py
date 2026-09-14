#!/usr/bin/env python3
"""Capture a sanitized one-shot Docker Compose resource snapshot."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def parse_stats(raw: str) -> list[dict[str, Any]]:
    """Parse Docker's JSON-lines stats output without retaining container IDs."""
    snapshots: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid docker stats JSON on line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"docker stats line {line_number} must be an object")
        name = str(item.get("Name") or item.get("name") or "").strip()
        cpu = str(item.get("CPUPerc") or item.get("cpu_percent") or "").strip()
        memory = str(item.get("MemUsage") or item.get("memory_usage") or "").strip()
        if not name:
            raise ValueError(f"docker stats line {line_number} has no service name")
        snapshots.append({"container": name.lstrip("/"), "cpu_percent": cpu, "memory": memory})
    return sorted(snapshots, key=lambda item: item["container"])


def aggregate_stats(samples: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Reduce repeated samples to peak CPU and the latest memory reading."""
    if not samples:
        return []
    expected_containers = {item["container"] for item in samples[0]}
    for index, sample in enumerate(samples[1:], start=2):
        if {item["container"] for item in sample} != expected_containers:
            raise ValueError(f"resource sample {index} contains a different container set")
    by_container: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        for item in sample:
            by_container.setdefault(item["container"], []).append(item)
    aggregated: list[dict[str, Any]] = []
    for container, items in sorted(by_container.items()):
        try:
            peak_cpu = max(float(str(item["cpu_percent"]).rstrip("%")) for item in items)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"resource CPU value is invalid for {container}") from exc
        aggregated.append(
            {
                "container": container,
                "cpu_percent": f"{peak_cpu:.3f}%",
                "memory": items[-1].get("memory", ""),
                "sample_count": len(items),
            }
        )
    return aggregated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compose-project", default=None)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--release-id", default=os.getenv("GITHUB_SHA", "local"))
    parser.add_argument("--operator", default=os.getenv("GITHUB_ACTOR", "local"))
    parser.add_argument("--topology", default="unknown")
    args = parser.parse_args(argv)
    if args.samples < 1 or args.interval_seconds < 0:
        parser.error("--samples must be at least 1 and --interval-seconds must be non-negative")
    command = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
    if args.compose_project:
        command.extend(["--filter", f"label=com.docker.compose.project={args.compose_project}"])
    try:
        samples = []
        for index in range(args.samples):
            completed = subprocess.run(command, capture_output=True, text=True, check=True)
            samples.append(parse_stats(completed.stdout))
            if index + 1 < args.samples and args.interval_seconds:
                time.sleep(args.interval_seconds)
        services = aggregate_stats(samples)
        payload = {
            "schema_version": 1,
            "release_id": args.release_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "operator": args.operator,
            "topology": args.topology,
            "sample_count": args.samples,
            "services": services,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"resource snapshot failed: {exc}", file=sys.stderr)
        return 2
    print(f"Resource snapshot written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
