"""Read a KEY=value from a .env file and print the value only."""

from __future__ import annotations

import pathlib
import sys


def main() -> int:
    if len(sys.argv) < 3:
        return 2
    env_path = pathlib.Path(sys.argv[1])
    key = str(sys.argv[2]).strip().upper()
    if not env_path.exists() or not key:
        return 0

    try:
        lines = env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    except Exception:
        return 0

    for raw in lines:
        line = raw.strip()
        if (not line) or line.startswith("#") or ("=" not in line):
            continue
        k, v = line.split("=", 1)
        if k.strip().upper() != key:
            continue
        value = v.strip().strip('"').strip("'")
        if value:
            print(value)
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
