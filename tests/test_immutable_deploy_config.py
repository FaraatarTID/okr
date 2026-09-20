from pathlib import Path

from scripts.check_immutable_deploy_config import find_mutable_references


def test_comments_are_not_treated_as_deployment_references(tmp_path: Path) -> None:
    target = tmp_path / "deploy/docker/compose.yml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "# image: ghcr.io/example/app:latest\nimage: ghcr.io/example/app:abc@sha256:"
        + "a" * 64
        + "\n",
        encoding="utf-8",
    )

    assert find_mutable_references(tmp_path) == []


def test_mutable_image_tag_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "deploy/docker/compose.yml"
    target.parent.mkdir(parents=True)
    target.write_text("image: ghcr.io/example/app:latest\n", encoding="utf-8")

    assert find_mutable_references(tmp_path) == ["deploy/docker/compose.yml:1"]
