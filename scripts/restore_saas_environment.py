"""Restore a provider-backed backup into an isolated rehearsal target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.backup_operations import RestoreManager, RestoreTarget, record_mapping, select_backup_provider
from src.saas.control_plane import ControlPlane
from src.saas.operator_credentials import resolve_operator_principal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-id", required=True)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--isolated-target", required=True)
    parser.add_argument("--state-file", type=Path, default=Path("tmp/saas-backups.json"))
    parser.add_argument("--credential-file", type=Path)
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--control-plane-state-file", type=Path, default=Path("tmp/saas-control-plane.json"))
    args = parser.parse_args(argv)
    provider = select_backup_provider(test_only=args.test_only, state_path=args.state_file)
    target = RestoreTarget(args.environment_id, args.isolated_target)
    result = RestoreManager(provider, operator=resolve_operator_principal(credential_file=args.credential_file), control_plane=ControlPlane(state_path=args.control_plane_state_file)).restore(args.backup_id, target)
    print(json.dumps({"action": "restore", **record_mapping(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
