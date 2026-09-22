"""Register a health-verified manual-provider tenant in the SQL control plane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.environment_contract import EnvironmentManifest
from src.saas.fleet_control_plane import SqlControlPlane
from src.saas.manual_darkube import ManualDarkubeAdapter
from src.saas.operator_credentials import resolve_operator_principal


def provision(
    manifest: EnvironmentManifest,
    plane: SqlControlPlane,
    *,
    provider_resource_id: str,
    incident_reference: str,
    health_evidence: dict,
    actor: str,
    signing_secret: str,
) -> dict:
    if str(health_evidence.get("status", "")).upper() != "PASSED":
        raise ValueError("tenant cannot become ready without PASSED health evidence")
    if not manifest.database_resource_id:
        raise ValueError("single-tenant manifest requires a database resource ID")
    action = (
        ManualDarkubeAdapter()
        .provision(manifest.environment_id, provider_resource_id, incident_reference)
        .evidence(signing_secret)
    )
    plane.register_ready_tenant(
        manifest.environment_id,
        manifest.customer_id,
        manifest.database_resource_id,
        provider_resource_id,
        actor=actor,
        evidence={"provider_action": action, "health_evidence": health_evidence},
    )
    return {"environment_id": manifest.environment_id, "state": "ready"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--control-plane-url", required=True)
    parser.add_argument("--provider-resource-id", required=True)
    parser.add_argument("--incident-reference", required=True)
    parser.add_argument("--health-evidence", type=Path, required=True)
    parser.add_argument("--credential-file", type=Path)
    parser.add_argument("--signing-secret", required=True)
    args = parser.parse_args(argv)
    operator = resolve_operator_principal(credential_file=args.credential_file)
    manifest = EnvironmentManifest.model_validate_json(
        args.manifest.read_text(encoding="utf-8")
    )
    result = provision(
        manifest,
        SqlControlPlane(args.control_plane_url),
        provider_resource_id=args.provider_resource_id,
        incident_reference=args.incident_reference,
        health_evidence=json.loads(args.health_evidence.read_text(encoding="utf-8")),
        actor=operator.principal,
        signing_secret=args.signing_secret,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
