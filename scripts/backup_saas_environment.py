"""Create or verify a provider-backed SaaS environment backup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import timedelta

from src.saas.backup_operations import BackupManager, record_mapping, select_backup_provider
from src.saas.control_plane import ControlPlane
from src.saas.operator_credentials import resolve_operator_principal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--environment-id", required=True)
    create.add_argument("--retention-class", default="standard")
    verify = sub.add_parser("verify")
    verify.add_argument("--backup-id", required=True)
    for command in (create, verify):
        command.add_argument("--state-file", type=Path, default=Path("tmp/saas-backups.json"))
        command.add_argument("--credential-file", type=Path)
        command.add_argument("--test-only", action="store_true")
        command.add_argument("--max-age-seconds", type=int, default=None)
        command.add_argument("--rpo-seconds", type=int, default=86400)
        command.add_argument("--rto-seconds", type=int, default=86400)
        command.add_argument("--control-plane-state-file", type=Path, default=Path("tmp/saas-control-plane.json"))
    args = parser.parse_args(argv)
    provider = select_backup_provider(test_only=args.test_only, state_path=args.state_file)
    manager = BackupManager(provider, operator=resolve_operator_principal(credential_file=args.credential_file), retention_class=getattr(args, "retention_class", "standard"), rpo_seconds=args.rpo_seconds, rto_seconds=args.rto_seconds, max_age=timedelta(seconds=args.max_age_seconds) if args.max_age_seconds is not None else None, control_plane=ControlPlane(state_path=args.control_plane_state_file))
    result = manager.create(args.environment_id) if args.action == "create" else manager.verify(args.backup_id)
    print(json.dumps({"action": args.action, **record_mapping(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
