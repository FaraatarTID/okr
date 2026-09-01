"""Run one local, metadata-only SaaS environment lifecycle operation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.environment_contract import EnvironmentManifest
from src.saas.control_plane import ControlPlane
from src.saas.provisioning import (
    LocalDisposableEnvironmentProvider,
    Provisioner,
)
from src.saas.operator_credentials import resolve_operator_principal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    provision_parser = subparsers.add_parser("provision")
    provision_parser.add_argument("--manifest", type=Path, required=True)
    suspend_parser = subparsers.add_parser("suspend")
    suspend_parser.add_argument("--environment-id", required=True)
    retire_parser = subparsers.add_parser("retire")
    retire_parser.add_argument("--environment-id", required=True)
    for operation_parser in (provision_parser, suspend_parser, retire_parser):
        operation_parser.add_argument("--credential-file", type=Path)
        operation_parser.add_argument(
            "--state-file", type=Path, default=Path("tmp/saas-environments.json")
        )
        operation_parser.add_argument("--control-plane-state-file", type=Path, default=Path("tmp/saas-control-plane.json"))
    args = parser.parse_args(argv)
    operator = resolve_operator_principal(credential_file=args.credential_file)
    provider = LocalDisposableEnvironmentProvider(args.state_file)
    provisioner = Provisioner(provider, operator=operator).with_control_plane(ControlPlane(state_path=args.control_plane_state_file))

    if args.operation == "provision":
        manifest = EnvironmentManifest.model_validate_json(
            args.manifest.read_text(encoding="utf-8")
        )
        result = provisioner.provision(manifest)
    else:
        result = getattr(provisioner, args.operation)(args.environment_id)

    print(json.dumps({"operation": args.operation, **result.__dict__}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
