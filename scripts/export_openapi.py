# ruff: noqa: E402
"""Export the backend OpenAPI schema to a versioned artifact.

Usage:
    python scripts/export_openapi.py [--out openapi.json]

The output is committed and used by spa-web type generation
(`npm --prefix spa-web run gen:api`). CI fails if the committed artifact
drifts from the live schema (see scripts/check_openapi_drift.py).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Non-production defaults so app import never requires real credentials.
os.environ.setdefault("OKR_ENV", "development")
os.environ.setdefault("OKR_BACKEND_ENFORCE_TOKEN", "false")
os.environ.setdefault("OKR_DATABASE_URL", "sqlite:///:memory:")

DEFAULT_OUT = ROOT_DIR / "spa-web" / "src" / "lib" / "api" / "openapi.json"


def export_schema(out_path: Path) -> int:
    import backend_app.main as backend_main

    schema = backend_main.app.openapi()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    path_count = len(schema.get("paths", {}))
    print(f"OpenAPI schema exported: {out_path} ({path_count} paths)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Export backend OpenAPI schema.")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output path (default: spa-web/src/lib/api/openapi.json)",
    )
    args = parser.parse_args()
    return export_schema(args.out.resolve())


if __name__ == "__main__":
    sys.exit(main())
