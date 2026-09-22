"""Run an isolated local SaaS release or rollback from JSON descriptors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.provisioning import LocalDisposableEnvironmentProvider
from src.saas.control_plane import ControlPlane
from src.saas.release_operations import (
    LocalRuntimeAdapter,
    ReleaseArtifact,
    ReleaseManager,
)
from src.saas.operator_credentials import resolve_operator_principal
from src.saas.fleet_control_plane import FleetReleaseGate, SqlControlPlane


def _artifact(path: str) -> ReleaseArtifact:
    return ReleaseArtifact.from_mapping(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "rollback", "compose-env"))
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--provisioning-state-file", required=True)
    parser.add_argument("--credential-file")
    parser.add_argument("--state-file", default="tmp/saas-release-state.json")
    parser.add_argument(
        "--control-plane-state-file", default="tmp/saas-control-plane.json"
    )
    parser.add_argument("--fleet-control-plane-url")
    parser.add_argument("--rollout-id", type=int)
    parser.add_argument("--incident-reference")
    args = parser.parse_args()

    provider = LocalDisposableEnvironmentProvider(args.provisioning_state_file)
    operator = resolve_operator_principal(credential_file=args.credential_file)
    if any(
        value is not None
        for value in (
            args.fleet_control_plane_url,
            args.rollout_id,
            args.incident_reference,
        )
    ) and not all(
        value is not None
        for value in (
            args.fleet_control_plane_url,
            args.rollout_id,
            args.incident_reference,
        )
    ):
        parser.error(
            "--fleet-control-plane-url, --rollout-id, and --incident-reference must be supplied together"
        )
    release_gate = (
        FleetReleaseGate(
            SqlControlPlane(args.fleet_control_plane_url),
            args.rollout_id,
            actor=operator.principal,
            incident_reference=args.incident_reference,
        )
        if args.fleet_control_plane_url is not None
        else None
    )
    manager = ReleaseManager(
        provider,
        LocalRuntimeAdapter(state_path=args.state_file),
        operator=operator,
        control_plane=ControlPlane(state_path=args.control_plane_state_file),
        release_gate=release_gate,
    )
    target = _artifact(args.artifact)
    if args.action == "compose-env":
        if not manager.runtime.is_registered(args.environment_id, target):
            raise SystemExit("artifact is not registered for the environment")
        print(
            json.dumps(
                manager.runtime.compose_environment(args.environment_id, target),
                sort_keys=True,
            )
        )
        return 0
    if args.action == "deploy":
        record = manager.deploy(args.environment_id, target)
    else:
        record = manager.rollback(args.environment_id, target)
    print(
        json.dumps(
            {
                "status": record.status.value,
                "record": {
                    field: getattr(record.record, field)
                    for field in record.record.__dataclass_fields__
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
