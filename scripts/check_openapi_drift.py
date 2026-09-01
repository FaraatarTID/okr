# ruff: noqa: E402
"""CI drift gate: fail if the committed OpenAPI artifact differs from live schema.

Run after scripts/export_openapi.py in CI. A non-zero exit means a backend
schema change was not accompanied by regenerated frontend types.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

# OpenAPI treats these collections as sets. Their order can vary between
# supported Python/Pydantic versions without changing the contract.
_ORDER_INSENSITIVE_KEYS = frozenset({"allOf", "anyOf", "enum", "oneOf", "required"})
_NON_CONTRACT_SCHEMAS = frozenset({"ValidationError"})


def _canonicalize(value, *, key: str | None = None):
    if isinstance(value, dict):
        return {
            name: _canonicalize(child, key=name)
            for name, child in sorted(value.items())
        }
    if isinstance(value, list):
        normalized = [_canonicalize(child, key=key) for child in value]
        if key in _ORDER_INSENSITIVE_KEYS:
            return sorted(normalized, key=lambda child: json.dumps(child, sort_keys=True))
        return normalized
    return value


def _contract_document(document: dict) -> dict:
    """Remove framework-owned schemas whose shape varies across FastAPI versions."""
    result = dict(document)
    components = dict(result.get("components", {}))
    schemas = dict(components.get("schemas", {}))
    for name in _NON_CONTRACT_SCHEMAS:
        schemas.pop(name, None)
    components["schemas"] = schemas
    result["components"] = components
    return result


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

    fresh_obj = backend_main.app.openapi()
    committed = artifact.read_text(encoding="utf-8")

    try:
        committed_obj = json_mod.loads(committed)
    except json_mod.JSONDecodeError:
        committed_obj = None

    if (
        committed_obj is not None
        and _canonicalize(_contract_document(fresh_obj))
        == _canonicalize(_contract_document(committed_obj))
    ):
        print("[PASS] OpenAPI artifact is up to date.")
        return 0

    # Show which paths changed for actionable output.
    try:
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
        fresh_components = set(fresh_obj.get("components", {}).get("schemas", {}).keys()) - _NON_CONTRACT_SCHEMAS
        committed_components = set(committed_obj.get("components", {}).get("schemas", {}).keys()) - _NON_CONTRACT_SCHEMAS
        changed_components = [
            name
            for name in sorted(fresh_components & committed_components)
            if _canonicalize(fresh_obj["components"]["schemas"][name])
            != _canonicalize(committed_obj["components"]["schemas"][name])
        ]
        if changed_components:
            print("Components changed:", ", ".join(changed_components[:20]))
    except Exception:
        pass

    print("[FAIL] OpenAPI artifact drifted from the live schema.")
    print("Fix: python scripts/export_openapi.py && git add " + str(artifact))
    return 1


if __name__ == "__main__":
    sys.exit(main())
