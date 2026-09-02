from __future__ import annotations

import json
import hashlib

import pytest

from scripts.verify_rollback_evidence import (
    RollbackEvidenceError,
    main,
    verify_rollback_manifest,
    verify_rollback_record,
)


COMMIT = "0123456789abcdef0123456789abcdef01234567"
DIGESTS = {
    name: f"sha256:{hashlib.sha256(name.encode()).hexdigest()}"
    for name in ("web", "bff", "backend")
}


def _payload_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def valid_manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "repository": "FaraatarTID/okr",
        "commit_sha": COMMIT,
        "images": {
            name: {
                "image": f"ghcr.io/faraatartid/okr/{name}:{COMMIT}",
                "digest": digest,
            }
            for name, digest in DIGESTS.items()
        },
    }
    manifest["attestation"] = {
        "provider": "github-actions",
        "evidence_id": "run-20260901-001",
        "algorithm": "provider-signed",
        "key_id": "release-key-2026",
        "signature": "release-signature-value-with-more-than-32-bytes",
        "issued_at": "2026-09-02T10:00:00Z",
        "signed_payload_sha256": _payload_digest(manifest),
    }
    return manifest


def cosign_references(manifest: dict[str, object]) -> list[str]:
    images = manifest["images"]
    assert isinstance(images, dict)
    return [f"{images[name]['image']}@{images[name]['digest']}" for name in sorted(images)]


def test_verifies_previous_known_good_manifest() -> None:
    result = verify_rollback_manifest(valid_manifest(), COMMIT, cosign_references(valid_manifest()))

    assert result == {
        "schema_version": 1,
        "commit_sha": COMMIT,
        "images": ["backend", "bff", "web"],
        "cosign_references": cosign_references(valid_manifest()),
        "verified": True,
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda manifest: manifest.update({"commit_sha": "b" * 40}), "synthetic"),
        (lambda manifest: manifest["images"].pop("backend"), "exactly web, bff, and backend"),
        (lambda manifest: manifest["images"].update({"debug": manifest["images"]["web"]}), "exactly web, bff, and backend"),
        (lambda manifest: manifest["images"]["web"].update({"digest": "sha256:bad"}), "digest"),
        (lambda manifest: manifest["images"]["bff"].update({"image": "docker.io/example/bff:tag"}), "GHCR"),
    ],
)
def test_rejects_invalid_previous_manifest(change, message: str) -> None:
    manifest = valid_manifest()
    change(manifest)

    with pytest.raises(RollbackEvidenceError, match=message):
        verify_rollback_manifest(manifest, COMMIT, [])


def test_rejects_cosign_reference_that_does_not_match_manifest() -> None:
    manifest = valid_manifest()
    references = cosign_references(manifest)
    references[0] = references[0].replace("@sha256:", "@sha256:" + "f")

    with pytest.raises(RollbackEvidenceError, match="Cosign reference"):
        verify_rollback_manifest(manifest, COMMIT, references)


def test_rejects_manifest_from_unexpected_repository() -> None:
    manifest = valid_manifest()
    manifest["repository"] = "another-owner/another-repository"

    with pytest.raises(RollbackEvidenceError, match="repository"):
        verify_rollback_manifest(manifest, COMMIT, expected_repository="FaraatarTID/okr")


def test_cli_writes_stable_rollback_evidence(tmp_path) -> None:
    manifest = valid_manifest()
    manifest_path = tmp_path / "release-manifest.json"
    output_path = tmp_path / "rollback-evidence.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert main(
        [
            "--manifest",
            str(manifest_path),
            "--commit-sha",
            COMMIT,
            *sum((["--cosign-reference", reference] for reference in cosign_references(manifest)), []),
            "--output",
            str(output_path),
        ]
    ) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["verified"] is True


def test_verifies_final_production_rollback_record() -> None:
    manifest = valid_manifest()
    record: dict[str, object] = {
        **manifest,
        "rollback": "rollback",
        "rollback_from_manifest_run_id": "123456789",
        "incident_reference": "INC-42",
        "approved_by": "release-operator",
        "approved_at": "2026-09-02T10:20:30Z",
        "cosign_references": cosign_references(manifest),
        "execution": {
            "status": "SUCCESS",
            "target_environment_id": "env-acme",
            "provider_operation_id": "darkube-rollback-20260902-001",
            "healthcheck": "PASSED",
            "observed_at": "2026-09-02T10:21:00Z",
        },
    }
    record["attestation"] = {
        "provider": "github-actions",
        "evidence_id": "run-20260902-002",
        "algorithm": "provider-signed",
        "key_id": "release-key-2026",
        "signature": "rollback-signature-value-with-more-than-32-bytes",
        "issued_at": "2026-09-02T10:21:30Z",
        "signed_payload_sha256": _payload_digest({key: value for key, value in record.items() if key != "attestation"}),
    }

    result = verify_rollback_record(record, COMMIT)

    assert result == {
        "schema_version": 1,
        "commit_sha": COMMIT,
        "images": ["backend", "bff", "web"],
        "cosign_references": cosign_references(manifest),
        "rollback": "rollback",
        "verified": True,
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rollback", "deploy", "rollback"),
        ("rollback_from_manifest_run_id", "", "manifest run ID"),
        ("approved_by", "", "approved by"),
        ("approved_at", "not-a-timestamp", "approved at"),
    ],
)
def test_rejects_invalid_final_production_rollback_record(field: str, value: str, message: str) -> None:
    manifest = valid_manifest()
    record = {
        **manifest,
        "rollback": "rollback",
        "rollback_from_manifest_run_id": "123456789",
        "incident_reference": "",
        "approved_by": "release-operator",
        "approved_at": "2026-09-02T10:20:30Z",
        "cosign_references": cosign_references(manifest),
        "execution": {
            "status": "SUCCESS",
            "target_environment_id": "env-acme",
            "provider_operation_id": "darkube-rollback-20260902-001",
            "healthcheck": "PASSED",
            "observed_at": "2026-09-02T10:21:00Z",
        },
    }
    record["attestation"] = {
        "provider": "github-actions",
        "evidence_id": "run-20260902-002",
        "algorithm": "provider-signed",
        "key_id": "release-key-2026",
        "signature": "rollback-signature-value-with-more-than-32-bytes",
        "issued_at": "2026-09-02T10:21:30Z",
        "signed_payload_sha256": _payload_digest({key: value for key, value in record.items() if key != "attestation"}),
    }
    record[field] = value

    with pytest.raises(RollbackEvidenceError, match=message):
        verify_rollback_record(record, COMMIT)


def test_rejects_failed_or_unsigned_rollback_execution() -> None:
    manifest = valid_manifest()
    record: dict[str, object] = {
        **manifest,
        "rollback": "rollback",
        "rollback_from_manifest_run_id": "123456789",
        "approved_by": "release-operator",
        "approved_at": "2026-09-02T10:20:30Z",
        "cosign_references": cosign_references(manifest),
        "execution": {
            "status": "FAILED",
            "target_environment_id": "env-acme",
            "provider_operation_id": "darkube-rollback-20260902-001",
            "healthcheck": "FAILED",
            "observed_at": "2026-09-02T10:21:00Z",
        },
    }
    with pytest.raises(RollbackEvidenceError, match="SUCCESS"):
        verify_rollback_record(record, COMMIT)


def test_rejects_synthetic_release_manifest() -> None:
    manifest = valid_manifest()
    manifest["commit_sha"] = "a" * 40

    with pytest.raises(RollbackEvidenceError, match="synthetic"):
        verify_rollback_manifest(manifest, "a" * 40, cosign_references(manifest))
