"""Attach a signed attestation to a derived evidence record.

A record built from an already-attested manifest cannot inherit that manifest's
signature: the signature covers the payload it was computed over, and adding the
approval or execution fields changes that payload. So each derived record is signed in
its own right, over its own contents, by the pipeline step that produced it.

This is the producer side of `scripts/attestation_verification.py`, and it is
deliberately separate from the verifiers so that a verifier never gains the ability to
sign what it is checking.

Usage:
    python scripts/attest_evidence.py --record production-rollback.json \
        --provider github-actions --key-id rollback-workflow \
        --evidence-id "rollback-2026-09-20"

Exit codes:
    0 - the record was signed in place
    1 - no signing key is configured, or the record is unusable
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.attestation_verification import (  # noqa: E402
    AttestationError,
    attach_attestation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--provider", default="github-actions")
    parser.add_argument("--key-id", required=True)
    parser.add_argument(
        "--evidence-id",
        default=os.environ.get("GITHUB_RUN_ID") or "",
        help="Defaults to GITHUB_RUN_ID. Recorded as attestation.evidence_id.",
    )
    args = parser.parse_args(argv)

    try:
        payload: Any = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ATTEST-EVIDENCE] could not read {args.record}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print(
            f"[ATTEST-EVIDENCE] {args.record} must contain a JSON object",
            file=sys.stderr,
        )
        return 1
    if not args.evidence_id:
        print(
            "[ATTEST-EVIDENCE] --evidence-id is required when GITHUB_RUN_ID is unset",
            file=sys.stderr,
        )
        return 1

    try:
        signed = attach_attestation(
            payload,
            provider=args.provider,
            key_id=args.key_id,
            evidence_id=args.evidence_id,
        )
    except AttestationError as exc:
        # Fail closed: an unsigned record must never be passed off as attested evidence.
        print(
            f"[ATTEST-EVIDENCE] refusing to write an unsigned record: {exc}",
            file=sys.stderr,
        )
        return 1

    args.record.write_text(
        json.dumps(signed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"[ATTEST-EVIDENCE] signed {args.record} with key_id={args.key_id}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
