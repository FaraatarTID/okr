#!/usr/bin/env python3
"""Run the disposable database migration smoke sequence."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_sequence(*, root: Path, runner: str = "uv") -> int:
    commands = (
        [runner, "run", "alembic", "upgrade", "head"],
        [runner, "run", "alembic", "current"],
        [runner, "run", "alembic", "upgrade", "head"],
    )
    for index, command in enumerate(commands, 1):
        print(f"[MIGRATION-SMOKE] step {index}/3: {command[2]}")
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode != 0:
            print(f"[MIGRATION-SMOKE] failed at step {index}", file=sys.stderr)
            return int(result.returncode)
    print("[MIGRATION-SMOKE] upgrade, head check, and idempotent rerun passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--runner", default="uv", help="Dependency runner, normally uv.")
    args = parser.parse_args(argv)
    return run_sequence(root=args.root.resolve(), runner=args.runner)


if __name__ == "__main__":
    raise SystemExit(main())
