from pathlib import Path

from scripts.check_saas_phase1_evidence import check


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def test_architecture_status_declares_fail_closed_customer_data_gate() -> None:
    content = _read("docs/architecture-status.md")

    assert "customer-data onboarding is **blocked**" in content
    for marker in (
        "provider-supported backup",
        "isolated target",
        "numeric measured backup freshness",
        "named platform/operations owner",
        "just saas-evidence",
        "disposable pre-release behavior",
    ):
        assert marker in content


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


def test_current_phase_evidence_cannot_authorize_customer_data() -> None:
    errors = check(ROOT / "docs/saas/phase-1-entry-evidence.md")
    joined = " ".join(errors).lower()

    assert "provider-issued verified backup evidence is required" in joined
    assert "successful isolated restore evidence is required" in joined
    assert "measured measured_rpo_seconds is required" in joined
    assert "measured measured_rto_seconds is required" in joined
    assert "named decision and operations owners are required" in joined
    assert "explicit real-data approval is required" in joined
