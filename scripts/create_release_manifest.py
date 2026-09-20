"""Assemble and validate immutable GHCR image release evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.attestation_verification import (  # noqa: E402
    ATTESTATION_SECRET_ENV,
    attach_attestation,
)

EXPECTED_IMAGES = {"web", "bff", "backend"}
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def build_manifest(
    fragments_dir: Path, repository: str, commit_sha: str
) -> dict[str, object]:
    if not _COMMIT_RE.fullmatch(commit_sha):
        raise ValueError("commit SHA must be a 40-character lowercase commit SHA")
    fragments = sorted(fragments_dir.glob("*.json"))
    if not fragments:
        raise ValueError(f"no release fragments found in {fragments_dir}")

    images: dict[str, dict[str, str]] = {}
    for path in fragments:
        fragment = json.loads(path.read_text(encoding="utf-8"))
        name = fragment.get("name")
        if name not in EXPECTED_IMAGES:
            raise ValueError(f"unexpected image name in {path}: {name!r}")
        if name in images:
            raise ValueError(f"duplicate image fragment: {name}")
        if fragment.get("commit_sha") != commit_sha:
            raise ValueError(f"{name} fragment has the wrong commit SHA")
        digest = fragment.get("digest")
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
            raise ValueError(f"{name} does not contain a registry digest")
        image = fragment.get("image")
        expected_suffix = f"/{name}:{commit_sha}"
        if (
            not isinstance(image, str)
            or not image.startswith("ghcr.io/")
            or not image.endswith(expected_suffix)
        ):
            raise ValueError(f"{name} image must use a GHCR commit SHA tag")
        if any(character.isspace() for character in image):
            raise ValueError(f"{name} does not contain a GHCR image reference")
        images[name] = {"image": image, "digest": digest}

    missing = EXPECTED_IMAGES - images.keys()
    if missing:
        raise ValueError(f"missing image fragments: {', '.join(sorted(missing))}")

    return {
        "schema_version": 1,
        "repository": repository,
        "commit_sha": commit_sha,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "images": {name: images[name] for name in sorted(images)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--attestation-provider",
        default="github-actions",
        help="Recorded as attestation.provider.",
    )
    parser.add_argument(
        "--attestation-key-id",
        default="release-manifest",
        help="Recorded as attestation.key_id.",
    )
    parser.add_argument(
        "--attestation-evidence-id",
        help="Recorded as attestation.evidence_id. Defaults to the commit SHA.",
    )
    parser.add_argument(
        "--require-attestation",
        action="store_true",
        help=(
            f"Fail instead of writing an unsigned manifest when {ATTESTATION_SECRET_ENV} "
            "is not configured. Release workflows pass this so an unverifiable manifest "
            "cannot be published."
        ),
    )
    args = parser.parse_args(argv)

    manifest = build_manifest(args.fragments, args.repository, args.commit_sha)
    secret = os.environ.get(ATTESTATION_SECRET_ENV, "")
    if secret:
        manifest = attach_attestation(
            manifest,
            provider=args.attestation_provider,
            key_id=args.attestation_key_id,
            evidence_id=args.attestation_evidence_id
            or f"ghcr-release-{args.commit_sha}",
            secret=secret,
        )
    elif args.require_attestation:
        print(
            "[RELEASE-MANIFEST] refusing to write an unsigned release manifest: "
            f"{ATTESTATION_SECRET_ENV} is not configured, so no verifier could ever "
            "accept the rollback evidence built from it.",
            file=sys.stderr,
        )
        return 1

    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Release manifest written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
