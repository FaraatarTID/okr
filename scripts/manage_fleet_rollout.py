"""Pause, resume, or inspect a SQL fleet rollout without database credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.fleet_control_plane import SqlControlPlane
from src.saas.operator_credentials import resolve_operator_principal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pause", "resume", "status"))
    parser.add_argument("--control-plane-url", required=True)
    parser.add_argument("--rollout-id", required=True, type=int)
    parser.add_argument("--credential-file", type=Path)
    args = parser.parse_args(argv)
    operator = resolve_operator_principal(credential_file=args.credential_file)
    plane = SqlControlPlane(args.control_plane_url)
    if args.action == "pause":
        plane.pause_rollout(args.rollout_id)
    elif args.action == "resume":
        plane.resume_rollout(args.rollout_id)
    status = plane.status(args.rollout_id)
    print(json.dumps({"actor": operator.principal, "action": args.action, **status}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
