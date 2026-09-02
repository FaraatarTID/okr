from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_environment_parity import build_report, main


ROOT = Path(__file__).resolve().parents[1]


def test_environment_parity_reports_repository_contract_and_provider_pending():
    report = build_report(ROOT)

    assert report["status"] == "PASS"
    assert report["provider_evidence"] == "PENDING_PROVIDER_EVIDENCE"
    assert {item["name"] for item in report["checks"]} >= {
        "ci-build-test-contract",
        "staging-immutable-image-contract",
        "production-promotion-contract",
        "local-compose-topology",
    }
    assert all(item["status"] == "PASS" for item in report["checks"])


def test_environment_parity_cli_can_emit_machine_readable_report(capsys):
    assert main(["--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["provider_evidence"] == "PENDING_PROVIDER_EVIDENCE"


def test_environment_parity_fails_when_ci_contract_is_missing(tmp_path: Path):
    for relative in (".github/workflows/ci.yml", ".github/workflows/darkube-prerelease.yml", ".github/workflows/promote-production.yml", "deploy/docker/docker-compose.yml"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    report = build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert any(item["status"] == "FAIL" for item in report["checks"])


def test_environment_parity_marks_absent_darkube_evidence_pending(tmp_path: Path):
    report = build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["provider_evidence"] == "PENDING_PROVIDER_EVIDENCE"
    assert report["provider_evidence_reason"] == "evidence_not_supplied"


def test_environment_parity_rejects_unverifiable_darkube_evidence(tmp_path: Path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")

    report = build_report(tmp_path, evidence_path=evidence, manifest_path=tmp_path / "manifest.json")

    assert report["status"] == "FAIL"
    assert report["provider_evidence"] == "FAIL"
    assert report["provider_evidence_reason"] == "evidence_not_verifiable"
