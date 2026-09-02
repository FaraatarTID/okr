"""Analyze a deterministic end-to-end page-load trace.

The trace is intentionally provider-independent. Capture mutually exclusive
stage durations from a browser/backend investigation, then run:

    python scripts/diagnose_page_load.py tests/fixtures/page_load_trace.json

The analyzer does not make optimization claims. It identifies where the
observed wall-clock time is accounted for and where instrumentation is still
missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

STAGES = ("browser", "bff", "backend", "database", "unattributed")


class TraceError(ValueError):
    """Raised when a page-load trace is incomplete or malformed."""


def analyze_trace(trace: dict[str, Any]) -> dict[str, Any]:
    total = trace.get("total_duration_ms")
    spans = trace.get("spans")
    if not isinstance(total, (int, float)) or total <= 0:
        raise TraceError("total_duration_ms must be a positive number")
    if not isinstance(spans, list) or not spans:
        raise TraceError("spans must be a non-empty list")

    by_stage = {stage: 0.0 for stage in STAGES}
    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            raise TraceError(f"spans[{index}] must be an object")
        stage = span.get("stage")
        duration = span.get("duration_ms")
        if stage not in STAGES[:-1]:
            raise TraceError(
                f"spans[{index}].stage must be one of: {', '.join(STAGES[:-1])}"
            )
        if not isinstance(duration, (int, float)) or duration < 0:
            raise TraceError(f"spans[{index}].duration_ms must be non-negative")
        by_stage[stage] += float(duration)

    accounted = sum(by_stage.values())
    unexplained = float(total) - accounted
    if unexplained < -0.01:
        raise TraceError(
            f"stage durations ({accounted:.2f} ms) exceed total ({float(total):.2f} ms)"
        )
    by_stage["unattributed"] = max(0.0, unexplained)
    dominant = max(by_stage, key=lambda stage: by_stage[stage])
    return {
        "page": trace.get("page", "unknown"),
        "total_duration_ms": round(float(total), 2),
        "stages_ms": {stage: round(value, 2) for stage, value in by_stage.items()},
        "dominant_stage": dominant,
        "attribution_pct": round((accounted / float(total)) * 100, 2),
        "diagnostic": (
            "instrument the missing layer before optimizing"
            if dominant == "unattributed"
            else f"investigate {dominant} stage first"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose a page-load trace JSON file.")
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        result = analyze_trace(json.loads(args.trace.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TraceError) as exc:
        print(f"page-load trace invalid: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
