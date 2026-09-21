"""Assemble and validate immutable GHCR image release evidence.

This manifest is deliberately **unsigned**, and that is a recorded decision rather than
an omission. Until 2026-09-21 the publisher attached an HMAC-SHA256 attestation from a
shared `OKR_RELEASE_MANIFEST_ATTESTATION_SECRET`. A6c removed it because it earned
nothing:

* The digest list it covered is already bound to Cosign keyless signatures, which the
  rollback workflow verifies against the OIDC identity of `publish-ghcr.yml` on `main`
  (`.github/workflows/rollback-production.yml`, plus
  `_validate_cosign_references` in `scripts/verify_rollback_evidence.py`). That check is
  asymmetric, externally verifiable, and needs no secret to be shared or rotated.
* A symmetric key held only by workflows in this repository, where one run both signs
  and verifies the same record, cannot distinguish an honest record from a forgery made
  by that same workflow.

See A6c in `docs/architecture-status.md`. The signature covered only
`schema_version`, `repository`, `commit_sha`, `created_at` and `images`; every member
that matters is re-derived and checked by the verifier anyway.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

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
    args = parser.parse_args(argv)

    manifest = build_manifest(args.fragments, args.repository, args.commit_sha)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Release manifest written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
