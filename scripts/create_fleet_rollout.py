"""Create a compatibility-checked canary rollout in the SQL control plane."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.fleet_control_plane import ReleaseMetadata, SqlControlPlane
from src.saas.operator_credentials import resolve_operator_principal


def create_rollout(
    plane: SqlControlPlane,
    release: ReleaseMetadata,
    environments: list[str],
    *,
    canary_count: int,
    actor: str,
    incident_reference: str,
) -> int:
    if not incident_reference.strip():
        raise ValueError("an incident or change reference is required")
    rollout_id = plane.create_rollout(release, environments, canary_count=canary_count)
    for environment_id in environments:
        plane.record_audit(
            environment_id,
            "ROLLOUT_CREATED",
            actor,
            {
                "rollout_id": rollout_id,
                "incident_reference": incident_reference,
                "release": asdict(release),
            },
        )
    return rollout_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-plane-url", required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--tenant", action="append", required=True)
    parser.add_argument("--canary-count", type=int, default=1)
    parser.add_argument("--incident-reference", required=True)
    parser.add_argument("--credential-file", type=Path)
    args = parser.parse_args(argv)
    release = ReleaseMetadata(**json.loads(args.release.read_text(encoding="utf-8")))
    operator = resolve_operator_principal(credential_file=args.credential_file)
    rollout_id = create_rollout(
        SqlControlPlane(args.control_plane_url),
        release,
        args.tenant,
        canary_count=args.canary_count,
        actor=operator.principal,
        incident_reference=args.incident_reference,
    )
    print(json.dumps({"rollout_id": rollout_id, "state": "canary"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
