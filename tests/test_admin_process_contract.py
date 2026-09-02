from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_admin_process_contract import build_report, main


ROOT = Path(__file__).resolve().parents[1]


def test_admin_process_contract_reports_explicit_one_off_operations():
    report = build_report(ROOT)

    assert report["status"] == "PASS"
    assert report["provider_recovery"] == "PENDING"
    assert {item["name"] for item in report["checks"]} >= {
        "migration-lint-operation",
        "environment-lifecycle-operation",
        "release-deploy-and-rollback-operation",
        "backup-and-restore-boundary",
    }
    assert all(item["status"] == "PASS" for item in report["checks"])


def test_admin_process_cli_emits_deterministic_json(capsys):
    assert main(["--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["provider_recovery"] == "PENDING"


def test_admin_process_contract_fails_when_required_operation_is_missing(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "verify_migration_lint.py").write_text("", encoding="utf-8")
    (scripts / "provision_saas_environment.py").write_text("", encoding="utf-8")
    (scripts / "deploy_saas_release.py").write_text("", encoding="utf-8")
    (scripts / "backup_saas_environment.py").write_text("", encoding="utf-8")
    (scripts / "restore_saas_environment.py").write_text("", encoding="utf-8")

    report = build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert any(item["status"] == "FAIL" for item in report["checks"])
