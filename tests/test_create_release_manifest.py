import hashlib
import json
from pathlib import Path

import pytest

from scripts.create_release_manifest import build_manifest, main
from scripts.verify_rollback_evidence import (
    RollbackEvidenceError,
    verify_rollback_manifest,
)

COMMIT = "a" * 40
# The rollback verifier rejects an all-identical commit SHA as synthetic, so the
# end-to-end case needs a realistic one.
REAL_COMMIT = "0123456789abcdef0123456789abcdef01234567"
# A6c removed the manifest HMAC, so nothing should read this any more. Several tests
# set it deliberately to prove the signing path is gone rather than merely unused.
RETIRED_SECRET_ENV = "OKR_SAAS_ATTESTATION_SECRET"
RETIRED_SECRET = "release-manifest-test-secret"
DIGESTS = {
    name: f"sha256:{hashlib.sha256(name.encode()).hexdigest()}"
    for name in ("web", "bff", "backend")
}


def write_fragments(
    directory: Path, *, digest: str = "sha256:" + "1" * 64, image_tag: str = COMMIT
) -> None:
    for name in ("web", "bff", "backend"):
        (directory / f"{name}.json").write_text(
            '{"name": "%s", "commit_sha": "%s", "image": "ghcr.io/faraatartid/okr/%s:%s", "digest": "%s"}'
            % (name, COMMIT, name, image_tag, digest),
            encoding="utf-8",
        )


def write_realistic_fragments(directory: Path) -> None:
    for name, digest in DIGESTS.items():
        (directory / f"{name}.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "commit_sha": REAL_COMMIT,
                    "image": f"ghcr.io/faraatartid/okr/{name}:{REAL_COMMIT}",
                    "digest": digest,
                }
            ),
            encoding="utf-8",
        )


def references(manifest: dict[str, object]) -> list[str]:
    images = manifest["images"]
    assert isinstance(images, dict)
    return [
        f"{images[name]['image']}@{images[name]['digest']}" for name in sorted(images)
    ]


def test_build_manifest_accepts_complete_digest_pinned_commit_pair(
    tmp_path: Path,
) -> None:
    write_fragments(tmp_path)

    manifest = build_manifest(tmp_path, "FaraatarTID/okr", COMMIT)

    assert manifest["commit_sha"] == COMMIT
    assert set(manifest["images"]) == {"web", "bff", "backend"}


@pytest.mark.parametrize(
    ("digest", "image_tag", "message"),
    [
        ("sha256:short", COMMIT, "digest"),
        ("sha256:" + "1" * 64, "latest", "commit SHA tag"),
    ],
)
def test_build_manifest_rejects_non_immutable_release_pair(
    tmp_path: Path, digest: str, image_tag: str, message: str
) -> None:
    write_fragments(tmp_path, digest=digest, image_tag=image_tag)

    with pytest.raises(ValueError, match=message):
        build_manifest(tmp_path, "FaraatarTID/okr", COMMIT)


def test_build_manifest_carries_no_attestation_even_with_the_secret_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-regression guard for A6c.

    Setting the retired secret must change nothing. If some future edit reintroduces an
    HMAC signed from this environment variable, this test fails.
    """
    monkeypatch.setenv(RETIRED_SECRET_ENV, RETIRED_SECRET)
    write_realistic_fragments(tmp_path)

    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)

    assert "attestation" not in manifest


def test_unsigned_manifest_is_accepted_with_verified_cosign_references(
    tmp_path: Path,
) -> None:
    """The A6c end-to-end assertion: Cosign alone is sufficient.

    This replaces the previous "signed manifest satisfies the rollback verifier" case.
    It is the evidence that removing the HMAC did not leave the rollback path with no
    way to accept a real release.
    """
    write_realistic_fragments(tmp_path)
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)

    result = verify_rollback_manifest(manifest, REAL_COMMIT, references(manifest))

    assert result["verified"] is True
    assert result["commit_sha"] == REAL_COMMIT
    assert result["cosign_references"] == sorted(references(manifest))


def test_unsigned_manifest_is_still_rejected_without_cosign_references(
    tmp_path: Path,
) -> None:
    """The gate must still fail closed. Dropping the HMAC must not drop the check."""
    write_realistic_fragments(tmp_path)
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)

    with pytest.raises(
        RollbackEvidenceError, match="signed Cosign references are required"
    ):
        verify_rollback_manifest(manifest, REAL_COMMIT, [])


def test_a_carried_attestation_member_no_longer_substitutes_for_cosign(
    tmp_path: Path,
) -> None:
    """A manifest that still carries an attestation block proves nothing on its own.

    Before A6c this payload would have passed on its signature. It must now be rejected
    for the same reason as any other manifest with no verified digests.
    """
    write_realistic_fragments(tmp_path)
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)
    manifest["attestation"] = {
        "provider": "github-actions",
        "evidence_id": "ghcr-release-1234567890",
        "algorithm": "provider-signed",
        "key_id": "publish-ghcr",
        "issued_at": "2026-09-21T00:00:00+00:00",
        "signed_payload_sha256": "sha256:" + "0" * 64,
        "signature": "hmac-sha256:" + "0" * 64,
    }

    with pytest.raises(
        RollbackEvidenceError, match="signed Cosign references are required"
    ):
        verify_rollback_manifest(manifest, REAL_COMMIT, [])


def test_a_digest_that_does_not_match_its_cosign_reference_is_rejected(
    tmp_path: Path,
) -> None:
    """Cosign references are cross-checked against the manifest, not merely present.

    This is the property that makes the HMAC redundant, so it is pinned explicitly.
    """
    write_realistic_fragments(tmp_path)
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)
    tampered = list(references(manifest))
    tampered[0] = tampered[0].rsplit("@", 1)[0] + "@sha256:" + "9" * 64

    with pytest.raises(RollbackEvidenceError, match="does not match the manifest"):
        verify_rollback_manifest(manifest, REAL_COMMIT, tampered)


def test_main_writes_an_unsigned_manifest_without_key_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Publishing no longer depends on a secret existing."""
    monkeypatch.delenv(RETIRED_SECRET_ENV, raising=False)
    write_realistic_fragments(tmp_path)
    output = tmp_path / "release-manifest.json"

    code = main(
        [
            "--fragments",
            str(tmp_path),
            "--output",
            str(output),
            "--repository",
            "FaraatarTID/okr",
            "--commit-sha",
            REAL_COMMIT,
        ]
    )

    assert code == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert "attestation" not in manifest
    assert manifest["commit_sha"] == REAL_COMMIT


def test_main_ignores_the_retired_secret_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(RETIRED_SECRET_ENV, RETIRED_SECRET)
    write_realistic_fragments(tmp_path)
    output = tmp_path / "release-manifest.json"

    code = main(
        [
            "--fragments",
            str(tmp_path),
            "--output",
            str(output),
            "--repository",
            "FaraatarTID/okr",
            "--commit-sha",
            REAL_COMMIT,
        ]
    )

    assert code == 0
    assert "attestation" not in json.loads(output.read_text(encoding="utf-8"))


def test_main_still_rejects_a_fragment_with_the_wrong_commit_sha(
    tmp_path: Path,
) -> None:
    """Removing signing must not remove the manifest's own validation."""
    write_fragments(tmp_path, image_tag=COMMIT)
    output = tmp_path / "release-manifest.json"

    with pytest.raises(ValueError, match="wrong commit SHA"):
        main(
            [
                "--fragments",
                str(tmp_path),
                "--output",
                str(output),
                "--repository",
                "FaraatarTID/okr",
                "--commit-sha",
                "b" * 40,
            ]
        )
    assert not output.exists()
