import json
import subprocess
import sys


def test_ops01_readiness_script_runs():
    result = subprocess.run(
        [sys.executable, "scripts/verify_ops01_readiness.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "OPS-01 readiness verification passed." in result.stdout


def test_ops01_backup_restore_drill_roundtrip(isolated_db):
    from backend_app.jobs import enqueue_job
    from src.audit import audit_log
    from src.database import export_database_backup, import_database_backup

    enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "ops01-check"},
        actor_username="ops-auditor",
        max_attempts=1,
    )
    audit_log("ops01-readiness", "backend", actor="ops-auditor", details={"ok": True})

    backup_payload = export_database_backup()
    payload = json.loads(backup_payload.decode("utf-8"))
    assert payload["format"] == "okr-db-backup/v1"
    assert payload["tables"]["async_job"]
    assert payload["tables"]["audit_event"]

    result = import_database_backup(payload)
    restored_counts = result["restored_counts"]
    assert int(restored_counts.get("async_job", 0)) >= 1
    assert int(restored_counts.get("audit_event", 0)) >= 1

    payload["format"] = "bad-format/v1"
    try:
        import_database_backup(payload)
        raise AssertionError("import_database_backup must reject wrong format")
    except ValueError:
        pass
