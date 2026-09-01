from __future__ import annotations

import json

import pytest

from scripts.verify_darkube_deployment import DeploymentVerificationError, main, verify_deployment


COMMIT = "a" * 40


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": "FaraatarTID/okr",
        "commit_sha": COMMIT,
        "images": {
            "web": {"image": f"ghcr.io/faraatartid/okr/web:{COMMIT}", "digest": "sha256:" + "1" * 64},
            "bff": {"image": f"ghcr.io/faraatartid/okr/bff:{COMMIT}", "digest": "sha256:" + "2" * 64},
            "backend": {
                "image": f"ghcr.io/faraatartid/okr/backend:{COMMIT}",
                "digest": "sha256:" + "3" * 64,
            },
        },
    }


def valid_evidence(manifest: dict[str, object]) -> dict[str, object]:
    images = manifest["images"]
    assert isinstance(images, dict)

    def copy_identity(name: str) -> dict[str, str]:
        identity = images[name]
        assert isinstance(identity, dict)
        return {"image": identity["image"], "digest": identity["digest"]}

    return {
        "schema_version": 1,
        "commit_sha": COMMIT,
        "namespace": "okr-pre-release",
        "applications": {
            "web": copy_identity("web"),
            "bff": copy_identity("bff"),
            "api": copy_identity("backend"),
            "worker": copy_identity("backend"),
        },
    }


def test_verifies_all_darkube_apps_against_manifest() -> None:
    result = verify_deployment(valid_manifest(), valid_evidence(valid_manifest()))

    assert result == {
        "schema_version": 1,
        "commit_sha": COMMIT,
        "namespace": "okr-pre-release",
        "applications": ["api", "bff", "web", "worker"],
        "verified": True,
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda evidence: evidence["applications"]["api"].update({"digest": "sha256:" + "9" * 64}), "digest"),
        (lambda evidence: evidence["applications"].pop("worker"), "exactly api, bff, web, and worker"),
        (lambda evidence: evidence["applications"].update({"debug": evidence["applications"]["web"]}), "exactly api, bff, web, and worker"),
        (lambda evidence: evidence.update({"commit_sha": "b" * 40}), "commit SHA"),
    ],
)
def test_rejects_non_matching_deployment_evidence(change, message: str) -> None:
    manifest = valid_manifest()
    evidence = valid_evidence(manifest)
    change(evidence)

    with pytest.raises(DeploymentVerificationError, match=message):
        verify_deployment(manifest, evidence)


def test_cli_writes_deterministic_verification_artifact(tmp_path) -> None:
    manifest_path = tmp_path / "release-manifest.json"
    evidence_path = tmp_path / "darkube-evidence.json"
    output_path = tmp_path / "deployment-verification.json"
    manifest = valid_manifest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    evidence_path.write_text(json.dumps(valid_evidence(manifest)), encoding="utf-8")

    assert main(["--manifest", str(manifest_path), "--evidence", str(evidence_path), "--output", str(output_path)]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["verified"] is True
