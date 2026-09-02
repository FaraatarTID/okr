from __future__ import annotations

import json

import pytest

from scripts.verify_rollback_evidence import (
    RollbackEvidenceError,
    main,
    verify_rollback_manifest,
    verify_rollback_record,
)


COMMIT = "a" * 40
DIGESTS = {name: f"sha256:{str(index) * 64}" for index, name in enumerate(("web", "bff", "backend"), 1)}


def valid_manifest() -> dict[str, object]:
    return {
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
        (lambda manifest: manifest.update({"commit_sha": "b" * 40}), "commit SHA"),
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
    record = {
        **manifest,
        "rollback": "rollback",
        "rollback_from_manifest_run_id": "123456789",
        "incident_reference": "INC-42",
        "approved_by": "release-operator",
        "approved_at": "2026-09-02T10:20:30Z",
    }

    result = verify_rollback_record(record, COMMIT)

    assert result == {
        "schema_version": 1,
        "commit_sha": COMMIT,
        "images": ["backend", "bff", "web"],
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
    }
    record[field] = value

    with pytest.raises(RollbackEvidenceError, match=message):
        verify_rollback_record(record, COMMIT)
