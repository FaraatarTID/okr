from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/ci.yml")


def test_ci_has_scoped_change_classes_and_required_aggregate() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for name in ("migration", "runtime", "contracts", "topology"):
        assert f"{name}: ${{{{ steps.filter.outputs.{name} }}}}" in text
    for job in (
        "migration-quality:",
        "contracts-quality:",
        "deployment-topology-quality:",
        "ci-result:",
    ):
        assert job in text
    assert "needs.migration-quality.result" in text
    assert "needs.contracts-quality.result" in text
    assert "needs.deployment-topology-quality.result" in text


def test_ci_caches_uv_and_playwright_dependencies() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "enable-cache: true" in text
    assert "cache: npm" in text
    assert "spa-web/.next/cache" in text
