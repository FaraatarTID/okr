"""Validate a known-good GHCR release manifest for rollback evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_IMAGES = ("web", "bff", "backend")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_RE = re.compile(r"^ghcr\.io/[^@\s:]+/[^@\s:]+/(web|bff|backend):([0-9a-f]{40})$")
_ATTESTATION_ALGORITHMS = {"ed25519", "rsa-pss-sha256", "provider-signed"}
_SYNTHETIC_MARKERS = ("test", "fixture", "synthetic", "mock", "local", "fake", "example")


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


def _reject_synthetic(value: str, label: str) -> None:
    if any(marker in value.casefold() for marker in _SYNTHETIC_MARKERS):
        raise RollbackEvidenceError(f"{label} must identify a real release operation")


def _payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import hashlib

    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _verify_attestation(payload: dict[str, Any], label: str = "attestation") -> None:
    attestation = _mapping(payload.get("attestation"), label)
    provider = _required_string(attestation.get("provider"), f"{label}.provider")
    evidence_id = _required_string(attestation.get("evidence_id"), f"{label}.evidence_id")
    algorithm = _required_string(attestation.get("algorithm"), f"{label}.algorithm").lower()
    _required_string(attestation.get("key_id"), f"{label}.key_id")
    signature = _required_string(attestation.get("signature"), f"{label}.signature")
    approved_at = _required_string(attestation.get("issued_at"), f"{label}.issued_at")
    try:
        parsed = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RollbackEvidenceError(f"{label}.issued_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RollbackEvidenceError(f"{label}.issued_at must include a timezone")
    _reject_synthetic(provider, f"{label}.provider")
    _reject_synthetic(evidence_id, f"{label}.evidence_id")
    if algorithm not in _ATTESTATION_ALGORITHMS:
        raise RollbackEvidenceError(f"{label}.algorithm is unsupported")
    if len(signature) < 32:
        raise RollbackEvidenceError(f"{label}.signature is incomplete")
    unsigned = {key: value for key, value in payload.items() if key != "attestation"}
    if attestation.get("signed_payload_sha256") != _payload_digest(unsigned):
        raise RollbackEvidenceError(f"{label} signed payload does not match evidence")


def _commit(value: Any, label: str) -> str:
    value = _required_string(value, label)
    if not _COMMIT_RE.fullmatch(value):
        raise RollbackEvidenceError(f"{label} must be a 40-character lowercase commit SHA")
    if len(set(value)) == 1:
        raise RollbackEvidenceError(f"{label} must not be a synthetic repeated value")
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
    if len(set(digest.removeprefix("sha256:"))) == 1:
        raise RollbackEvidenceError(f"manifest.images.{name}.digest must not be synthetic")
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
    manifest: dict[str, Any],
    expected_commit_sha: str,
    cosign_references: list[str] | None = None,
    expected_repository: str | None = None,
    require_attestation: bool = True,
) -> dict[str, Any]:
    """Return deterministic rollback evidence or raise on any mismatch."""
    manifest = _mapping(manifest, "manifest")
    if manifest.get("schema_version") != 1:
        raise RollbackEvidenceError("manifest.schema_version must be 1")
    expected_commit_sha = _commit(expected_commit_sha, "expected commit SHA")
    if expected_repository is not None:
        repository = _required_string(manifest.get("repository"), "manifest.repository")
        if repository != expected_repository:
            raise RollbackEvidenceError("manifest repository does not match expected repository")
    manifest_commit_sha = _commit(manifest.get("commit_sha"), "manifest.commit_sha")
    if manifest_commit_sha != expected_commit_sha:
        raise RollbackEvidenceError("manifest commit SHA does not match expected commit SHA")

    images = _mapping(manifest.get("images"), "manifest.images")
    if set(images) != set(REQUIRED_IMAGES):
        raise RollbackEvidenceError("manifest images must be exactly web, bff, and backend")
    expected = {name: _image_identity(images[name], name, manifest_commit_sha) for name in REQUIRED_IMAGES}
    verified_cosign = _validate_cosign_references(cosign_references or [], expected)
    if not verified_cosign:
        raise RollbackEvidenceError("signed Cosign references are required for rollback evidence")
    if require_attestation:
        _verify_attestation(manifest)

    result: dict[str, Any] = {
        "schema_version": 1,
        "commit_sha": manifest_commit_sha,
        "images": sorted(REQUIRED_IMAGES),
        "verified": True,
    }
    if verified_cosign:
        result["cosign_references"] = verified_cosign
    return result


def verify_rollback_record(
    record: dict[str, Any], expected_commit_sha: str, expected_repository: str | None = None
) -> dict[str, Any]:
    """Validate the final approval record uploaded by the rollback workflow."""
    record = _mapping(record, "rollback record")
    cosign_references = record.get("cosign_references")
    if not isinstance(cosign_references, list):
        raise RollbackEvidenceError("rollback record.cosign_references must be a complete signed list")
    manifest_result = verify_rollback_manifest(
        record,
        expected_commit_sha,
        cosign_references=cosign_references,
        expected_repository=expected_repository,
        require_attestation=False,
    )
    if record.get("rollback") != "rollback":
        raise RollbackEvidenceError("rollback record.rollback must be 'rollback'")
    run_id = _required_string(record.get("rollback_from_manifest_run_id"), "rollback record manifest run ID")
    if not run_id.isdigit() or int(run_id) <= 0:
        raise RollbackEvidenceError("rollback record manifest run ID must be a positive integer")
    _required_string(record.get("approved_by"), "rollback record approved by")
    approved_at = _required_string(record.get("approved_at"), "rollback record approved at")
    try:
        parsed = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RollbackEvidenceError("rollback record approved at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RollbackEvidenceError("rollback record approved at must include a timezone")
    execution = _mapping(record.get("execution"), "rollback record.execution")
    if execution.get("status") != "SUCCESS":
        raise RollbackEvidenceError("rollback record.execution.status must be SUCCESS")
    for field in ("target_environment_id", "provider_operation_id", "healthcheck", "observed_at"):
        _required_string(execution.get(field), f"rollback record.execution.{field}")
    if execution.get("healthcheck") != "PASSED":
        raise RollbackEvidenceError("rollback record.execution.healthcheck must be PASSED")
    _reject_synthetic(execution["provider_operation_id"], "rollback record.execution.provider_operation_id")
    _verify_attestation(record, "rollback record.attestation")
    return {**manifest_result, "rollback": "rollback"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--record", type=Path)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--repository")
    parser.add_argument("--cosign-reference", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        source_path = args.record or args.manifest
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if args.record:
            if args.cosign_reference:
                raise RollbackEvidenceError("Cosign references are only valid with --manifest")
            result = verify_rollback_record(payload, args.commit_sha, args.repository)
        else:
            result = verify_rollback_manifest(
                payload, args.commit_sha, args.cosign_reference, args.repository
            )
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
