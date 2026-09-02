from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dependency_manifest_is_checked_against_uv_authority() -> None:
    source = (ROOT / "scripts" / "check_dependency_manifest.py").read_text(
        encoding="utf-8"
    )
    assert "tomllib" in source
    assert "backend_app/requirements.txt" in source
    assert "pyproject.toml" in source
    assert "uv.lock" in source


def test_release_manifests_reject_unresolved_kubernetes_digests() -> None:
    source = (ROOT / "scripts" / "render_k8s_release.py").read_text(
        encoding="utf-8"
    )
    assert "REPLACE_WITH_RELEASE_DIGEST" in source
    assert "64" in source


def test_dependency_check_compares_locked_versions() -> None:
    source = (ROOT / "scripts" / "check_dependency_manifest.py").read_text(
        encoding="utf-8"
    )
    assert "_locked_versions" in source
    assert "declared=" in source
