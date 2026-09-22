"""Create the standalone SQL fleet control-plane schema in its dedicated database."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saas.fleet_control_plane import SqlControlPlane


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-plane-url", required=True)
    args = parser.parse_args(argv)
    SqlControlPlane(args.control_plane_url).create_schema()
    print("Fleet control-plane schema is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
