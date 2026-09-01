"""Validate a known-good GHCR release manifest for rollback evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_IMAGES = ("web", "bff", "backend")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_RE = re.compile(r"^ghcr\.io/[^@\s:]+/[^@\s:]+/(web|bff|backend):([0-9a-f]{40})$")


class RollbackEvidenceError(ValueError):
    """Raised when a rollback manifest cannot be trusted as release evidence."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RollbackEvidenceError(f"{label} must be an object")
    return value


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RollbackEvidenceError(f"{label} must be a non-empty string")
    return value


def _commit(value: Any, label: str) -> str:
    value = _required_string(value, label)
    if not _COMMIT_RE.fullmatch(value):
        raise RollbackEvidenceError(f"{label} must be a 40-character lowercase commit SHA")
    return value


def _image_identity(value: Any, name: str, commit_sha: str) -> tuple[str, str]:
    image = _mapping(value, f"manifest.images.{name}")
    image_ref = _required_string(image.get("image"), f"manifest.images.{name}.image")
    match = _IMAGE_RE.fullmatch(image_ref)
    if not match or match.group(1) != name or match.group(2) != commit_sha:
        raise RollbackEvidenceError(
            f"manifest.images.{name}.image must be the GHCR {name} image tagged with the commit SHA"
        )
    digest = _required_string(image.get("digest"), f"manifest.images.{name}.digest")
    if not _DIGEST_RE.fullmatch(digest):
        raise RollbackEvidenceError(f"manifest.images.{name}.digest must be a sha256 registry digest")
    return image_ref, digest


def _validate_cosign_references(
    references: list[str], expected: dict[str, tuple[str, str]]
) -> list[str]:
    if not references:
        return []

    actual: dict[str, str] = {}
    for reference in references:
        if not isinstance(reference, str):
            raise RollbackEvidenceError("Cosign reference must be a string")
        if "@" not in reference:
            raise RollbackEvidenceError("Cosign reference must use image@sha256:digest form")
        image_ref, digest = reference.rsplit("@", 1)
        match = _IMAGE_RE.fullmatch(image_ref)
        if not match or not _DIGEST_RE.fullmatch(digest):
            raise RollbackEvidenceError("Cosign reference must be a valid GHCR image@sha256:digest")
        name = match.group(1)
        if name in actual:
            raise RollbackEvidenceError(f"duplicate Cosign reference for {name}")
        if expected[name] != (image_ref, digest):
            raise RollbackEvidenceError(f"Cosign reference for {name} does not match the manifest")
        actual[name] = digest

    if set(actual) != set(REQUIRED_IMAGES):
        raise RollbackEvidenceError("Cosign references must contain exactly web, bff, and backend")
    return [f"{expected[name][0]}@{expected[name][1]}" for name in sorted(REQUIRED_IMAGES)]


def verify_rollback_manifest(
    manifest: dict[str, Any], expected_commit_sha: str, cosign_references: list[str] | None = None
) -> dict[str, Any]:
    """Return deterministic rollback evidence or raise on any mismatch."""
    manifest = _mapping(manifest, "manifest")
    if manifest.get("schema_version") != 1:
        raise RollbackEvidenceError("manifest.schema_version must be 1")
    expected_commit_sha = _commit(expected_commit_sha, "expected commit SHA")
    manifest_commit_sha = _commit(manifest.get("commit_sha"), "manifest.commit_sha")
    if manifest_commit_sha != expected_commit_sha:
        raise RollbackEvidenceError("manifest commit SHA does not match expected commit SHA")

    images = _mapping(manifest.get("images"), "manifest.images")
    if set(images) != set(REQUIRED_IMAGES):
        raise RollbackEvidenceError("manifest images must be exactly web, bff, and backend")
    expected = {name: _image_identity(images[name], name, manifest_commit_sha) for name in REQUIRED_IMAGES}
    verified_cosign = _validate_cosign_references(cosign_references or [], expected)

    result: dict[str, Any] = {
        "schema_version": 1,
        "commit_sha": manifest_commit_sha,
        "images": sorted(REQUIRED_IMAGES),
        "verified": True,
    }
    if verified_cosign:
        result["cosign_references"] = verified_cosign
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--cosign-reference", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = verify_rollback_manifest(manifest, args.commit_sha, args.cosign_reference)
    except (RollbackEvidenceError, OSError, json.JSONDecodeError) as exc:
        print(f"[ROLLBACK-EVIDENCE] verification failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    print("[ROLLBACK-EVIDENCE] known-good release manifest verified", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
