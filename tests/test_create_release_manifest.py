from pathlib import Path

import pytest

from scripts.create_release_manifest import build_manifest


COMMIT = "a" * 40


def write_fragments(directory: Path, *, digest: str = "sha256:" + "1" * 64, image_tag: str = COMMIT) -> None:
    for name in ("web", "bff", "backend"):
        (directory / f"{name}.json").write_text(
            '{"name": "%s", "commit_sha": "%s", "image": "ghcr.io/faraatartid/okr/%s:%s", "digest": "%s"}'
            % (name, COMMIT, name, image_tag, digest),
            encoding="utf-8",
        )


def test_build_manifest_accepts_complete_digest_pinned_commit_pair(tmp_path: Path) -> None:
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
