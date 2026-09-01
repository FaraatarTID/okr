"""Fail closed unless the Phase 1 production evidence bundle is complete."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re

REQUIRED_FIELDS = {"schema_version", "decision", "provisioning", "release", "backup", "restore", "rpo_rto", "owners", "real_data_approval"}
REQUIRED_ATTESTATION_FIELDS = {"provider", "backup_id", "restore_id", "environment_id", "customer_id", "backup_target", "release_identity", "provisioning_identity", "artifact_digests", "measured_rollback_seconds", "measured_rpo_seconds", "measured_rto_seconds", "decision_owner", "operations_owner", "signature"}
FORBIDDEN_MARKERS = re.compile(r"(?:local|test|synthetic|fake|dummy|fixture|mock)", re.IGNORECASE)
OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


def canonical_attestation_payload(attestation: dict[str, object]) -> bytes:
    return json.dumps(
        {key: value for key, value in attestation.items() if key != "signature"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def check(path: Path, *, secret: str | None = None) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return ["missing structured evidence JSON block"]
    try:
        evidence = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        return [f"invalid structured evidence JSON: {error.msg}"]
    if not isinstance(evidence, dict):
        return ["structured evidence JSON must be an object"]
    errors: list[str] = []
    errors.extend(f"missing structured evidence field: {field}" for field in sorted(REQUIRED_FIELDS - evidence.keys()))
    if errors:
        return errors
    if evidence["schema_version"] != 1:
        errors.append("unsupported structured evidence schema_version")
    if evidence["decision"].get("status") != "APPROVED" or not str(evidence["decision"].get("owner", "")).strip():
        errors.append("decision approval and named owner are required")
    if not str(evidence["provisioning"].get("environment_id", "")).strip() or evidence["provisioning"].get("idempotent") is not True:
        errors.append("provisioning environment_id and idempotency evidence are required")
    artifacts = evidence["release"].get("artifacts", [])
    digest = re.compile(r"^sha256:[0-9a-f]{64}$")
    if len(artifacts) < 2 or any(not str(item.get("version", "")).strip() or not digest.fullmatch(str(item.get("digest", ""))) for item in artifacts):
        errors.append("two immutable artifact versions with SHA-256 digests are required")
    if evidence["release"].get("rollback_result") != "passed":
        errors.append("successful rollback result is required")
    measured_rollback = evidence["release"].get("measured_rollback_seconds")
    if not isinstance(measured_rollback, (int, float)) or isinstance(measured_rollback, bool) or measured_rollback < 0:
        errors.append("measured rollback seconds are required")
    backup = evidence["backup"]
    if not str(backup.get("provider", "")).strip() or not str(backup.get("backup_id", "")).strip() or backup.get("verified") is not True:
        errors.append("provider-issued verified backup evidence is required")
    restore = evidence["restore"]
    if restore.get("result") != "passed" or not str(restore.get("target", "")).strip() or not str(restore.get("restore_id", "")).strip():
        errors.append("successful isolated restore evidence is required")
    for field in ("measured_rpo_seconds", "measured_rto_seconds"):
        value = evidence["rpo_rto"].get(field)
        if not isinstance(value, (int, float)) or value < 0:
            errors.append(f"measured {field} is required")
    owners = evidence["owners"]
    if not _named(owners.get("decision")) or not _named(owners.get("operations")):
        errors.append("named decision and operations owners are required")
    if evidence["real_data_approval"] is not True:
        errors.append("explicit real-data approval is required")
    attestation = evidence.get("attestation")
    if not isinstance(attestation, dict):
        errors.append("machine-readable production attestation is required")
    else:
        errors.extend(f"missing attestation field: {field}" for field in sorted(REQUIRED_ATTESTATION_FIELDS - attestation.keys()))
        provider = str(attestation.get("provider", "")).strip()
        if not provider or FORBIDDEN_MARKERS.search(provider):
            errors.append("explicit production provider is required; local/test providers are forbidden")
        for field, label in (("backup_id", "provider-issued backup ID"), ("restore_id", "provider-issued restore ID")):
            value = str(attestation.get(field, "")).strip()
            if not value or not OPAQUE_ID.fullmatch(value) or FORBIDDEN_MARKERS.search(value):
                errors.append(f"{label} is required and synthetic/test IDs are forbidden")
        for field in ("environment_id", "customer_id", "backup_target", "release_identity", "provisioning_identity"):
            if not str(attestation.get(field, "")).strip():
                errors.append(f"attested {field} is required")
        digests = attestation.get("artifact_digests")
        if not isinstance(digests, list) or len(digests) < 2 or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", str(value)) for value in digests):
            errors.append("attested immutable artifact digests are required")
        elif {str(item.get("digest", "")) for item in artifacts} != set(digests):
            errors.append("attested artifact digests must match the release artifact digests")
        for field in ("measured_rollback_seconds", "measured_rpo_seconds", "measured_rto_seconds"):
            value = attestation.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                errors.append(f"attested {field} is required")
        if not _named(attestation.get("decision_owner")) or not _named(attestation.get("operations_owner")):
            errors.append("attested named decision and operations owners are required")
        if provider != str(backup.get("provider", "")).strip() or str(attestation.get("backup_id", "")).strip() != str(backup.get("backup_id", "")).strip():
            errors.append("attested provider and backup ID must match structured backup evidence")
        if str(attestation.get("restore_id", "")).strip() != str(restore.get("restore_id", "")).strip():
            errors.append("attested restore ID must match structured restore evidence")
        if attestation.get("environment_id") != evidence["provisioning"].get("environment_id"):
            errors.append("attested environment ID must match structured provisioning evidence")
        if attestation.get("customer_id") != evidence["provisioning"].get("customer_id"):
            errors.append("attested customer ID must match structured provisioning evidence")
        if attestation.get("backup_target") != evidence["backup"].get("backup_target"):
            errors.append("attested backup target must match structured backup evidence")
        if attestation.get("release_identity") != evidence["release"].get("release_identity"):
            errors.append("attested release identity must match structured release evidence")
        if attestation.get("provisioning_identity") != evidence["provisioning"].get("provisioning_identity"):
            errors.append("attested provisioning identity must match structured provisioning evidence")
        if attestation.get("measured_rollback_seconds") != measured_rollback:
            errors.append("attested rollback measurement must match structured release evidence")
        if attestation.get("measured_rpo_seconds") != evidence["rpo_rto"].get("measured_rpo_seconds") or attestation.get("measured_rto_seconds") != evidence["rpo_rto"].get("measured_rto_seconds"):
            errors.append("attested RPO/RTO measurements must match structured evidence")
        if attestation.get("decision_owner") != owners.get("decision") or attestation.get("operations_owner") != owners.get("operations"):
            errors.append("attested owners must match structured owner evidence")
        signature = str(attestation.get("signature", "")).strip()
        configured_secret = secret or os.environ.get("OKR_SAAS_ATTESTATION_SECRET", "")
        expected = "hmac-sha256:" + hmac.new(configured_secret.encode("utf-8"), canonical_attestation_payload(attestation), hashlib.sha256).hexdigest() if configured_secret else ""
        if not configured_secret:
            errors.append("attestation signature verification secret is required")
        elif not hmac.compare_digest(signature, expected):
            errors.append("attestation signature is invalid")
    return errors


def _named(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.upper() != "UNASSIGNED" and not FORBIDDEN_MARKERS.search(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("docs/saas/phase-1-entry-evidence.md"))
    args = parser.parse_args(argv)
    if not args.path.exists():
        print(f"SaaS Phase 1 evidence check failed: missing {args.path}")
        return 1
    errors = check(args.path)
    if errors:
        print("SaaS Phase 1 evidence check failed.")
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("SaaS Phase 1 evidence check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
