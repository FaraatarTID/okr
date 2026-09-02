#!/usr/bin/env python3
"""Render Kubernetes release manifests with validated image digests."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DIGEST = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"
_SOURCES = {
    "deployment-backend-api.yaml": "deploy/k8s/deployment-backend-api.yaml",
    "deployment-backend-worker.yaml": "deploy/k8s/deployment-backend-worker.yaml",
}


def _validate_digest(value: str, label: str) -> str:
    digest = value.removeprefix("sha256:")
    if not _DIGEST.fullmatch(digest):
        raise ValueError(f"{label} must be a 64-character hexadecimal sha256 digest")
    return digest


def render(*, api_digest: str, worker_digest: str, output_dir: Path) -> None:
    values = {
        "deployment-backend-api.yaml": _validate_digest(api_digest, "api_digest"),
        "deployment-backend-worker.yaml": _validate_digest(worker_digest, "worker_digest"),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, relative in _SOURCES.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        rendered = source.replace(_PLACEHOLDER, values[filename])
        if _PLACEHOLDER in rendered:
            raise ValueError(f"unresolved digest placeholder remains in {filename}")
        (output_dir / filename).write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    render(
        api_digest=args.api_digest,
        worker_digest=args.worker_digest,
        output_dir=args.output_dir,
    )
    print(f"Rendered Kubernetes release manifests to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
