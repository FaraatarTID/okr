import hashlib
import json
from pathlib import Path

import pytest

from scripts.create_release_manifest import attach_attestation, build_manifest, main
from scripts.verify_rollback_evidence import (
    RollbackEvidenceError,
    verify_rollback_manifest,
)


COMMIT = "a" * 40
# The rollback verifier rejects an all-identical commit SHA as synthetic, so the
# end-to-end case needs a realistic one.
REAL_COMMIT = "0123456789abcdef0123456789abcdef01234567"
SECRET = "release-manifest-test-secret"
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


def test_build_manifest_alone_carries_no_attestation(tmp_path: Path) -> None:
    """`build_manifest` stays pure; signing is a separate, explicit step."""
    write_realistic_fragments(tmp_path)

    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)

    assert "attestation" not in manifest


def test_signed_manifest_satisfies_the_rollback_verifier(tmp_path: Path) -> None:
    """The whole point of signing: the rollback verifier accepts the result.

    This is the end-to-end assertion the release pipeline depends on. Before signing was
    added, no manifest this script could produce would ever pass `--manifest`, so the
    rollback evidence steps could not succeed for any release.
    """
    write_realistic_fragments(tmp_path)
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)

    signed = attach_attestation(
        manifest,
        provider="github-actions",
        key_id="publish-ghcr",
        evidence_id="ghcr-release-1234567890",
        secret=SECRET,
    )

    result = verify_rollback_manifest(
        signed, REAL_COMMIT, references(signed), secret=SECRET
    )

    assert result["verified"] is True
    assert result["commit_sha"] == REAL_COMMIT


def test_signed_manifest_is_rejected_after_a_field_changes(tmp_path: Path) -> None:
    """Adding a member after signing invalidates the attestation, as it must.

    The self-digest check catches this before the signature is reached, which is the
    intended order: it names the payload mismatch instead of blaming the key.
    """
    write_realistic_fragments(tmp_path)
    manifest = build_manifest(tmp_path, "FaraatarTID/okr", REAL_COMMIT)
    signed = attach_attestation(
        manifest,
        provider="github-actions",
        key_id="publish-ghcr",
        evidence_id="ghcr-release-1234567890",
        secret=SECRET,
    )
    signed["rollback"] = "rollback"

    with pytest.raises(RollbackEvidenceError, match="does not match evidence"):
        verify_rollback_manifest(signed, REAL_COMMIT, references(signed), secret=SECRET)


def test_main_signs_when_the_secret_is_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_realistic_fragments(tmp_path)
    output = tmp_path / "release-manifest.json"
    monkeypatch.setenv("OKR_SAAS_ATTESTATION_SECRET", SECRET)

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
            "--attestation-provider",
            "github-actions",
            "--attestation-key-id",
            "publish-ghcr",
            "--attestation-evidence-id",
            "ghcr-release-1234567890",
            "--require-attestation",
        ]
    )

    assert code == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["attestation"]["key_id"] == "publish-ghcr"
    assert manifest["attestation"]["algorithm"] == "provider-signed"


def test_main_refuses_to_write_an_unsigned_manifest_when_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fail closed: a release must not publish a manifest no verifier can accept."""
    write_realistic_fragments(tmp_path)
    output = tmp_path / "release-manifest.json"
    monkeypatch.delenv("OKR_SAAS_ATTESTATION_SECRET", raising=False)

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
            "--require-attestation",
        ]
    )

    assert code == 1
    assert not output.exists()
    assert "refusing to write an unsigned release manifest" in capsys.readouterr().err


def test_main_writes_an_unsigned_manifest_when_not_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Local and dry-run use stays possible without key material."""
    write_realistic_fragments(tmp_path)
    output = tmp_path / "release-manifest.json"
    monkeypatch.delenv("OKR_SAAS_ATTESTATION_SECRET", raising=False)

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
