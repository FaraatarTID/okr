"""Register an isolated restore target or restore a backup into one."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.backup_operations import (
    RestoreManager,
    RestoreTarget,
    record_mapping,
    select_backup_provider,
    validate_restore_target,
)
from src.saas.control_plane import ControlPlane
from src.saas.operator_credentials import resolve_operator_principal


def _add_common_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--environment-id", required=True)
    command.add_argument("--isolated-target", required=True)
    command.add_argument("--state-file", type=Path, default=Path("tmp/saas-backups.json"))
    command.add_argument("--credential-file", type=Path)
    command.add_argument("--test-only", action="store_true")
    command.add_argument(
        "--control-plane-state-file",
        type=Path,
        default=Path("tmp/saas-control-plane.json"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    register = sub.add_parser(
        "register-target",
        help="register an isolated restore target so a restore can target it",
    )
    _add_common_arguments(register)
    restore = sub.add_parser("restore", help="restore a backup into a registered isolated target")
    restore.add_argument("--backup-id", required=True)
    _add_common_arguments(restore)
    args = parser.parse_args(argv)

    # Resolving the operator first keeps both actions authenticated and fails
    # closed before any provider or state mutation.
    operator = resolve_operator_principal(credential_file=args.credential_file)
    provider = select_backup_provider(test_only=args.test_only, state_path=args.state_file)
    target = RestoreTarget(args.environment_id, args.isolated_target)

    if args.action == "register-target":
        validate_restore_target(target)
        provider.register_target(target)
        print(
            json.dumps(
                {
                    "action": "register-target",
                    "environment_id": target.environment_id,
                    "database_target": target.database_target,
                    "registered": provider.is_target_registered(target),
                    "operator": operator.principal,
                },
                sort_keys=True,
            )
        )
        return 0

    manager = RestoreManager(
        provider,
        operator=operator,
        control_plane=ControlPlane(state_path=args.control_plane_state_file),
    )
    result = manager.restore(args.backup_id, target)
    print(json.dumps({"action": "restore", **record_mapping(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
