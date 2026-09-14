from __future__ import annotations

from scripts.check_generated_artifacts import find_violations


def test_generated_artifact_gate_rejects_tracked_outputs() -> None:
    tracked = [
        "pytest-results.xml",
        "pytest-results-local.xml",
        "spa-web/coverage/coverage-summary.json",
        "spa-bff/.cache/tsconfig.tsbuildinfo",
        "spa-web/.next/build-manifest.json",
        "src/__pycache__/module.pyc",
        ".pytest_cache/CACHEDIR.TAG",
        "tmp/saas-environments.json",
        "deploy/docker/.env",
    ]
    violations = find_violations(tracked)
    assert len(violations) == len(tracked)


def test_generated_artifact_gate_allows_sources_and_examples() -> None:
    tracked = [
        "backend_app/main.py",
        "spa-web/package.json",
        "package-lock.json",
        "deploy/docker/.env.example",
        "deploy/docker/.env.mycompany.example",
        "deploy/docker/.env.saas.example",
    ]
    assert find_violations(tracked) == []
