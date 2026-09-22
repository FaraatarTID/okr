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


def test_contract_quality_runs_for_every_openapi_boundary_input() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    # The contract lane must run for a backend schema implementation change,
    # SPA typed-wrapper change, BFF policy/proxy change, and its own generator.
    # Otherwise one layer can become stale while only an unrelated lane runs.
    for path in (
        "'backend_app/**'",
        "'spa-web/src/lib/api/**'",
        "'spa-bff/src/**'",
        "'scripts/generate_spa_operation_routes.py'",
    ):
        assert path in text

    contract_block = text.split("  contracts-quality:", 1)[1].split(
        "  deployment-topology-quality:", 1
    )[0]
    for gate in (
        "scripts/check_openapi_drift.py",
        "scripts/generate_bff_allowlist.py --check",
        "scripts/generate_spa_operation_routes.py --check",
        "scripts/check_spa_api_contract_boundary.py",
        "npm --prefix spa-web run check:gen:api",
        "npm --prefix spa-bff run check:gen:api",
    ):
        assert gate in contract_block
