"""Coverage for the release-pair verifier, which had none and could never pass.

`verify_release_pair` called `verify_rollback_manifest` with no Cosign references at
all, so every manifest it was given was rejected before any comparison happened. It was
also referenced by no enforcement surface and by no test, which is how that survived.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.attestation_verification import attach_attestation
from scripts.create_release_manifest import build_manifest
from scripts.verify_release_pair import ReleasePairError, main, verify_release_pair


COMMIT_NEW = "1" * 39 + "2"
COMMIT_OLD = "3" * 39 + "4"
SECRET = "release-pair-test-secret"


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OKR_SAAS_ATTESTATION_SECRET", SECRET)


def _manifest(tmp_path: Path, commit: str, suffix: str) -> dict[str, object]:
    fragments = tmp_path / f"fragments-{suffix}"
    fragments.mkdir()
    for name in ("web", "bff", "backend"):
        digest = hashlib.sha256(f"{name}-{suffix}".encode()).hexdigest()
        (fragments / f"{name}.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "commit_sha": commit,
                    "image": f"ghcr.io/faraatartid/okr/{name}:{commit}",
                    "digest": f"sha256:{digest}",
                }
            ),
            encoding="utf-8",
        )
    return attach_attestation(
        build_manifest(fragments, "FaraatarTID/okr", commit),
        provider="github-actions",
        key_id="publish-ghcr",
        evidence_id=f"ghcr-release-{suffix}",
        secret=SECRET,
    )


def _references(manifest: dict[str, object]) -> list[str]:
    images = manifest["images"]
    assert isinstance(images, dict)
    return [
        f"{images[name]['image']}@{images[name]['digest']}" for name in sorted(images)
    ]


def test_verifies_a_distinct_pair_when_both_carry_references(tmp_path: Path) -> None:
    new = _manifest(tmp_path, COMMIT_NEW, "new")
    old = _manifest(tmp_path, COMMIT_OLD, "old")

    result = verify_release_pair(new, old, _references(new), _references(old))

    assert result["verified"] is True
    assert result["status"] == "DRY_RUN_ONLY"
    assert result["deployment_performed"] is False


def test_rejects_a_pair_without_references(tmp_path: Path) -> None:
    """This is the call shape that made the script unrunnable."""
    new = _manifest(tmp_path, COMMIT_NEW, "new")
    old = _manifest(tmp_path, COMMIT_OLD, "old")

    with pytest.raises(ReleasePairError, match="signed Cosign references are required"):
        verify_release_pair(new, old)


def test_rejects_a_pair_sharing_one_commit(tmp_path: Path) -> None:
    new = _manifest(tmp_path, COMMIT_NEW, "new")
    same = _manifest(tmp_path, COMMIT_NEW, "same")

    with pytest.raises(ReleasePairError, match="different commit SHAs"):
        verify_release_pair(new, same, _references(new), _references(same))


def test_rejects_references_belonging_to_the_other_manifest(tmp_path: Path) -> None:
    """Each manifest pins different digests, so one reference list cannot serve both."""
    new = _manifest(tmp_path, COMMIT_NEW, "new")
    old = _manifest(tmp_path, COMMIT_OLD, "old")

    with pytest.raises(ReleasePairError, match="does not match the manifest"):
        verify_release_pair(new, old, _references(old), _references(new))


def test_cli_verifies_a_pair_and_refuses_one_without_references(tmp_path: Path) -> None:
    new = _manifest(tmp_path, COMMIT_NEW, "new")
    old = _manifest(tmp_path, COMMIT_OLD, "old")
    new_path = tmp_path / "new.json"
    old_path = tmp_path / "old.json"
    new_path.write_text(json.dumps(new), encoding="utf-8")
    old_path.write_text(json.dumps(old), encoding="utf-8")
    output = tmp_path / "pair.json"

    argv = ["--new-manifest", str(new_path), "--old-manifest", str(old_path)]
    for reference in _references(new):
        argv += ["--new-cosign-reference", reference]
    for reference in _references(old):
        argv += ["--old-cosign-reference", reference]

    assert main(argv + ["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["verified"] is True
    assert main(["--new-manifest", str(new_path), "--old-manifest", str(old_path)]) == 2
