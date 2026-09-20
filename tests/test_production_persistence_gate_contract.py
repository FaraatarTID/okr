from pathlib import Path

from scripts.check_saas_phase1_evidence import check


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def test_architecture_status_declares_conditionally_reviewed_single_tenant_gate() -> None:
    content = _read("docs/architecture-status.md")

    assert "blocked pending provider evidence" in content
    assert "hamravesh/darkube provider evidence" in content
    assert "no approval is active" in content
    for marker in (
        "provider-supported backup",
        "isolated target",
        "named decision owner",
        "named platform/operations owner",
        "just saas-evidence",
        "single-tenant",
    ):
        assert marker in content.lower()


def test_saas_roadmap_and_runbook_preserve_the_same_gate() -> None:
    roadmap = _read("docs/architecture/ENTERPRISE_SAAS_ROADMAP.md")
    runbook = _read("docs/migration-rollback-runbook.md")

    for content in (roadmap, runbook):
        assert "provider-supported" in content
        assert "isolated restore" in content
        assert "rpo/rto" in content
        assert "platform/operations owner" in content
        assert "fail-closed" in content or "fail closed" in content
        assert "disposable pre-saas" in content


def test_current_phase_evidence_fails_closed_until_provider_evidence_exists() -> None:
    errors = check(ROOT / "docs/saas/phase-1-entry-evidence.md", secret="phase1-ops-secret")
    assert errors
    assert any("decision approval" in error for error in errors)
    assert any("isolated restore evidence" in error for error in errors)
    assert any("explicit real-data approval" in error for error in errors)
