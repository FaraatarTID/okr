# ruff: noqa: E402
"""CI drift gate: fail if the committed OpenAPI artifact differs from live schema.

Run after scripts/export_openapi.py in CI. A non-zero exit means a backend
schema change was not accompanied by regenerated frontend types.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OpenAPI artifact drift.")
    parser.add_argument(
        "--artifact",
        type=Path,
        default=ROOT_DIR / "spa-web" / "src" / "lib" / "api" / "openapi.json",
    )
    args = parser.parse_args()
    artifact = args.artifact.resolve()

    if not artifact.exists():
        print(f"[FAIL] OpenAPI artifact missing: {artifact}")
        print("Run: python scripts/export_openapi.py")
        return 1

    # Regenerate into memory and compare against the committed artifact.
    import os

    os.environ.setdefault("OKR_ENV", "development")
    os.environ.setdefault("OKR_BACKEND_ENFORCE_TOKEN", "false")
    os.environ.setdefault("OKR_DATABASE_URL", "sqlite:///:memory:")

    sys.path.insert(0, str(ROOT_DIR))
    import backend_app.main as backend_main
    import json as json_mod

    fresh = json_mod.dumps(
        backend_main.app.openapi(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    committed = artifact.read_text(encoding="utf-8")

    if fresh == committed:
        print("[PASS] OpenAPI artifact is up to date.")
        return 0

    # Show which paths changed for actionable output.
    try:
        fresh_obj = json_mod.loads(fresh)
        committed_obj = json_mod.loads(committed)
        fresh_paths = set(fresh_obj.get("paths", {}).keys())
        committed_paths = set(committed_obj.get("paths", {}).keys())
        added = sorted(fresh_paths - committed_paths)
        removed = sorted(committed_paths - fresh_paths)
        if added:
            print("Paths added:", ", ".join(added))
        if removed:
            print("Paths removed:", ", ".join(removed))
        common = fresh_paths & committed_paths
        changed = [
            p
            for p in sorted(common)
            if json_mod.dumps(fresh_obj["paths"][p], sort_keys=True)
            != json_mod.dumps(committed_obj["paths"][p], sort_keys=True)
        ]
        if changed:
            print("Paths changed:", ", ".join(changed[:20]))
    except Exception:
        pass

    print("[FAIL] OpenAPI artifact drifted from the live schema.")
    print("Fix: python scripts/export_openapi.py && git add " + str(artifact))
    return 1


if __name__ == "__main__":
    sys.exit(main())
