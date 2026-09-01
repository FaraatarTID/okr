"""Verify sanitized Darkube deployment image evidence against a release manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


APPLICATIONS = ("api", "bff", "web", "worker")
MANIFEST_IMAGES = ("web", "bff", "backend")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DeploymentVerificationError(ValueError):
    """Raised when deployment evidence does not match the release manifest."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeploymentVerificationError(f"{label} must be an object")
    return value


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeploymentVerificationError(f"{label} must be a non-empty string")
    return value


def _validate_commit(value: Any, label: str) -> str:
    commit = _required_string(value, label)
    if not _COMMIT_RE.fullmatch(commit):
        raise DeploymentVerificationError(f"{label} must be a 40-character lowercase commit SHA")
    return commit


def _image_identity(value: Any, label: str) -> dict[str, str]:
    image = _mapping(value, label)
    image_ref = _required_string(image.get("image"), f"{label}.image")
    digest = _required_string(image.get("digest"), f"{label}.digest")
    if not _DIGEST_RE.fullmatch(digest):
        raise DeploymentVerificationError(f"{label}.digest must be a sha256 registry digest")
    return {"image": image_ref, "digest": digest}


def verify_deployment(manifest: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Return stable verification evidence or raise on any contract mismatch."""
    manifest = _mapping(manifest, "manifest")
    evidence = _mapping(evidence, "evidence")
    if manifest.get("schema_version") != 1 or evidence.get("schema_version") != 1:
        raise DeploymentVerificationError("manifest and evidence schema_version must be 1")

    manifest_commit = _validate_commit(manifest.get("commit_sha"), "manifest.commit_sha")
    evidence_commit = _validate_commit(evidence.get("commit_sha"), "evidence.commit_sha")
    if evidence_commit != manifest_commit:
        raise DeploymentVerificationError("evidence commit SHA does not match manifest commit SHA")

    manifest_images = _mapping(manifest.get("images"), "manifest.images")
    if set(manifest_images) != set(MANIFEST_IMAGES):
        raise DeploymentVerificationError("manifest images must be exactly web, bff, and backend")
    expected = {name: _image_identity(manifest_images[name], f"manifest.images.{name}") for name in MANIFEST_IMAGES}

    applications = _mapping(evidence.get("applications"), "evidence.applications")
    if set(applications) != set(APPLICATIONS):
        raise DeploymentVerificationError("applications must contain exactly api, bff, web, and worker")
    actual = {name: _image_identity(applications[name], f"evidence.applications.{name}") for name in APPLICATIONS}

    for application in ("web", "bff"):
        if actual[application] != expected[application]:
            raise DeploymentVerificationError(f"{application} image or digest does not match manifest")
    for application in ("api", "worker"):
        if actual[application] != expected["backend"]:
            raise DeploymentVerificationError(f"{application} image or digest does not match manifest backend")

    namespace = _required_string(evidence.get("namespace"), "evidence.namespace")
    return {
        "schema_version": 1,
        "commit_sha": manifest_commit,
        "namespace": namespace,
        "applications": list(APPLICATIONS),
        "verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = verify_deployment(manifest, evidence)
    except (DeploymentVerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"[DARKUBE-DEPLOYMENT] verification failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    print("[DARKUBE-DEPLOYMENT] exact image digests verified", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
