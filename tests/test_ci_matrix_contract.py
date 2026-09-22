from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _passes_curl_retries(workflow: str) -> bool:
    """Whether a workflow passes `curl-retries` to the Cosign installer.

    Matches a YAML key line rather than a bare substring, so a comment explaining
    why the input is not used does not itself count as using it.
    """
    return any(
        line.strip().startswith("curl-retries:") for line in workflow.splitlines()
    )


def test_ci_classifies_backend_frontend_and_shared_changes() -> None:
    text = _workflow_text()

    assert "uses: dorny/paths-filter@v3" in text
    assert "backend:" in text
    assert "frontend:" in text
    assert "shared:" in text
    assert "unclassified:" in text
    assert "'backend_app/**'" in text
    assert "'spa-web/**'" in text
    assert "'spa-bff/**'" in text
    assert "'.github/**'" in text
    assert "'deploy/**'" in text
    assert "- '!spa-web/**'" in text


def test_ci_has_a_documentation_only_lane() -> None:
    text = _workflow_text()

    assert "docs: ${{ steps.filter.outputs.docs }}" in text
    assert "              - 'docs/**'" in text
    assert "              - '**/*.md'" in text
    assert "  docs-quality:" in text
    assert "if: ${{ needs.changes.outputs.docs == 'true' }}" in text


def test_release_workflows_ignore_documentation_only_pushes() -> None:
    root = WORKFLOW.parents[1]
    for name in ("publish-ghcr.yml", "docker-deploy.yml", "darkube-prerelease.yml"):
        workflow = (root / "workflows" / name).read_text(encoding="utf-8")
        assert "paths-ignore:" in workflow
        assert "      - 'docs/**'" in workflow
        assert "      - '**/*.md'" in workflow


def test_release_workflows_use_supported_cosign_installer_line() -> None:
    root = WORKFLOW.parents[1]
    release_workflows = (
        "publish-ghcr.yml",
        "verify-ghcr-signatures.yml",
        "promote-production.yml",
        "rollback-production.yml",
    )
    for name in release_workflows:
        workflow = (root / "workflows" / name).read_text(encoding="utf-8")
        assert (
            "uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2"
            in workflow
        )
        # `curl-retries` is not an input `sigstore/cosign-installer` accepts; GitHub
        # reports the valid inputs as cosign-release, install-dir and use-sudo. This
        # assertion previously required the line to be PRESENT, which certified an
        # install retry that never occurred. It now requires the inert input to stay
        # out, so the same false assurance cannot be reintroduced. Matching a key
        # rather than a bare substring keeps the explanation comments legitimate.
        assert not _passes_curl_retries(workflow)
        assert "run: cosign version" in workflow
        assert "sigstore/cosign-installer@v3." not in workflow


def test_cosign_health_workflow_exercises_the_same_installer_contract() -> None:
    root = WORKFLOW.parents[1]
    workflow = (root / "workflows" / "cosign-health.yml").read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert (
        "uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2"
        in workflow
    )
    # See the note in the release-workflow test: the input is not accepted by the
    # action, so asserting its presence asserted nothing real.
    assert not _passes_curl_retries(workflow)
    assert "cosign version" in workflow


def test_heavy_jobs_escalate_shared_changes_and_skip_unrelated_areas() -> None:
    text = _workflow_text()

    migration_condition = "needs.changes.outputs.migration == 'true' || needs.changes.outputs.shared == 'true' || needs.changes.outputs.unclassified == 'true'"
    runtime_condition = "needs.changes.outputs.runtime == 'true' || needs.changes.outputs.shared == 'true' || needs.changes.outputs.unclassified == 'true'"
    frontend_condition = "needs.changes.outputs.frontend == 'true' || needs.changes.outputs.shared == 'true' || needs.changes.outputs.unclassified == 'true'"

    assert text.count("needs: changes") >= 3
    assert text.count(migration_condition) >= 1
    assert text.count(runtime_condition) >= 1
    assert text.count(frontend_condition) >= 2
    assert "  ci-result:" in text
    assert "if: always()" in text
    assert "intentionally skipped matrix jobs are neutral" in text
