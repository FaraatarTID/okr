"""Validate sanitized backup and isolated-restore evidence without provider calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class RecoveryEvidenceError(ValueError):
    """Raised when recovery evidence is incomplete, unsafe, or inconsistent."""


_CHECKSUM_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATUSES = {"SUCCESS", "FAILED"}


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecoveryEvidenceError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecoveryEvidenceError(f"{label} must be a non-empty string")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    raw = _string(value, label)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryEvidenceError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RecoveryEvidenceError(f"{label} must include a timezone")
    return parsed


def _seconds(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RecoveryEvidenceError(f"{label} must be a non-negative integer")
    return value


def _status(record: dict[str, Any], label: str) -> str:
    value = _string(record.get("status"), f"{label}.status").upper()
    if value not in _STATUSES:
        raise RecoveryEvidenceError(f"{label}.status must be SUCCESS or FAILED")
    if value == "FAILED":
        _string(record.get("failure_reason"), f"{label}.failure_reason")
    return value


def _checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def verify_recovery_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Return a stable verification summary or raise on any evidence violation."""
    evidence = _object(evidence, "evidence")
    if evidence.get("schema_version") != 1:
        raise RecoveryEvidenceError("schema_version must be 1")

    environment_id = _string(evidence.get("environment_id"), "environment_id")
    database = _object(evidence.get("database"), "database")
    database_identity = _string(database.get("identity"), "database.identity")
    _string(database.get("provider"), "database.provider")

    backup = _object(evidence.get("backup"), "backup")
    backup_id = _string(backup.get("backup_id"), "backup.backup_id")
    backup_status = _status(backup, "backup")
    created_at = _timestamp(backup.get("created_at"), "backup.created_at")
    verified_at = _timestamp(backup.get("verified_at"), "backup.verified_at")
    if verified_at < created_at:
        raise RecoveryEvidenceError("backup timestamps are out of order")

    checksum_payload = _object(backup.get("checksum_payload"), "backup.checksum_payload")
    expected_payload = {
        "backup_id": backup_id,
        "database_identity": database_identity,
        "environment_id": environment_id,
        "created_at": backup.get("created_at"),
    }
    if checksum_payload != expected_payload:
        raise RecoveryEvidenceError("backup.checksum_payload does not match database identity")
    checksum = _string(backup.get("checksum"), "backup.checksum")
    if not _CHECKSUM_RE.fullmatch(checksum) or checksum != _checksum(checksum_payload):
        raise RecoveryEvidenceError("backup checksum does not match canonical evidence payload")

    restore = _object(evidence.get("restore"), "restore")
    restore_status = _status(restore, "restore")
    target = _object(restore.get("target"), "restore.target")
    target_identity = _string(target.get("identity"), "restore.target.identity")
    if target_identity == database_identity:
        raise RecoveryEvidenceError("restore target must be different from the source database")
    if target.get("environment_id") != environment_id:
        raise RecoveryEvidenceError("restore target environment must match database environment")
    if target.get("isolation") != "isolated":
        raise RecoveryEvidenceError("restore target must be isolated")
    if target.get("live") is not False:
        raise RecoveryEvidenceError("restore target live flag must be false")

    restore_started = _timestamp(restore.get("started_at"), "restore.started_at")
    restore_completed = _timestamp(restore.get("completed_at"), "restore.completed_at")
    if restore_started < verified_at or restore_completed < restore_started:
        raise RecoveryEvidenceError("restore timestamps are out of order")
    if restore.get("restored_checksum") != checksum:
        raise RecoveryEvidenceError("restore checksum does not match backup checksum")

    rpo_target = _seconds(evidence.get("rpo_target_seconds"), "rpo_target_seconds")
    rto_target = _seconds(evidence.get("rto_target_seconds"), "rto_target_seconds")
    measured_rpo = _seconds(evidence.get("measured_rpo_seconds"), "measured_rpo_seconds")
    measured_rto = _seconds(evidence.get("measured_rto_seconds"), "measured_rto_seconds")
    if measured_rpo > rpo_target:
        raise RecoveryEvidenceError("measured RPO exceeds RPO target")
    if measured_rto > rto_target:
        raise RecoveryEvidenceError("measured RTO exceeds RTO target")

    overall_status = _string(evidence.get("status"), "status").upper()
    if overall_status not in {"PASSED", "FAILED"}:
        raise RecoveryEvidenceError("status must be PASSED or FAILED")
    expected_status = "PASSED" if backup_status == restore_status == "SUCCESS" else "FAILED"
    if overall_status != expected_status:
        raise RecoveryEvidenceError("status does not match backup and restore statuses")
    _string(evidence.get("operator"), "operator")

    return {
        "schema_version": 1,
        "environment_id": environment_id,
        "database_identity": database_identity,
        "backup_id": backup_id,
        "restore_target_identity": target_identity,
        "rpo_target_seconds": rpo_target,
        "rto_target_seconds": rto_target,
        "measured_rpo_seconds": measured_rpo,
        "measured_rto_seconds": measured_rto,
        "backup_status": backup_status,
        "restore_status": restore_status,
        "status": overall_status,
        "verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = verify_recovery_evidence(evidence)
    except (OSError, json.JSONDecodeError, RecoveryEvidenceError) as exc:
        print(f"[RECOVERY-EVIDENCE] verification failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    print("[RECOVERY-EVIDENCE] sanitized backup/restore evidence verified", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
