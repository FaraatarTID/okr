from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


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


def test_heavy_jobs_escalate_shared_changes_and_skip_unrelated_areas() -> None:
    text = _workflow_text()

    backend_condition = "needs.changes.outputs.backend == 'true' || needs.changes.outputs.shared == 'true' || needs.changes.outputs.unclassified == 'true'"
    frontend_condition = "needs.changes.outputs.frontend == 'true' || needs.changes.outputs.shared == 'true' || needs.changes.outputs.unclassified == 'true'"

    assert text.count("needs: changes") >= 3
    assert text.count(backend_condition) >= 2
    assert text.count(frontend_condition) >= 2
    assert "  ci-result:" in text
    assert "if: always()" in text
    assert "intentionally skipped matrix jobs are neutral" in text
