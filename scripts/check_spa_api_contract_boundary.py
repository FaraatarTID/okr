"""Fail when SPA API modules bypass the centralized backend transport."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SPA_SOURCE_DIR = ROOT / "spa-web" / "src"
API_DIR = ROOT / "spa-web" / "src" / "lib" / "api"
TRANSPORT = API_DIR / "http.ts"
OPENAPI_PATH = API_DIR / "openapi.json"
BFF_POLICY_PATH = ROOT / "spa-bff" / "src" / "route-policy.json"
BFF_SESSION_FETCH = re.compile(r"\bfetch\s*\(\s*[`\"']/api/session/")
FETCH_REFERENCE = re.compile(r"\bfetch\b")
BRACKET_FETCH_REFERENCE = re.compile(
    r"\b(?:globalThis|window)\s*\[\s*[\"']fetch[\"']\s*\]"
)
LEGACY_BACKEND_FETCH = re.compile(r"\bbackendFetch\s*\(")
OPERATION_REFERENCE = re.compile(r'\boperation:\s*["\']([^"\']+)["\']')
# These endpoints are owned by the BFF, rather than the backend OpenAPI API.
LOCAL_RESPONSE_TYPES = {"AuthResponse", "SessionMeResponse"}
# Generic OpenAPI façade utilities, not endpoint-specific hand-authored contracts.
OPENAPI_FACADE_RESPONSE_TYPES = {
    "BackendSuccessResponse",
    "BackendErrorResponse",
    "BackendValidationError",
}
SERVER_SIDE_BFF_PROXY_MODULES = {
    ROOT / "spa-web" / "src" / "lib" / "bff-proxy.ts",
    ROOT / "spa-web" / "src" / "app" / "api" / "healthz" / "route.ts",
}


def _bff_operation_ids() -> set[str]:
    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    policy = json.loads(BFF_POLICY_PATH.read_text(encoding="utf-8"))
    operation_ids: set[str] = set()
    for route in policy["routes"]:
        path_item = schema["paths"][route["pathTemplate"]]
        for method in route["methods"]:
            operation_id = path_item[method.lower()].get("operationId")
            if operation_id:
                operation_ids.add(str(operation_id))
    return operation_ids


def _api_sources() -> list[Path]:
    sources = [
        path
        for extension in ("*.ts", "*.tsx")
        for path in API_DIR.rglob(extension)
        if "generated" not in path.relative_to(API_DIR).parts
        and ".test." not in path.name
        and ".spec." not in path.name
    ]
    return sorted(set(sources))


def _spa_sources() -> list[Path]:
    # Test fixtures commonly replace API_DIR alone; preserve that focused scope
    # when the fixture is outside the repository SPA root.
    source_root = SPA_SOURCE_DIR if API_DIR.is_relative_to(SPA_SOURCE_DIR) else API_DIR
    sources = [
        path
        for extension in ("*.ts", "*.tsx")
        for path in source_root.rglob(extension)
        if "generated" not in path.relative_to(source_root).parts
        and ".test." not in path.name
        and ".spec." not in path.name
    ]
    return sorted(set(sources))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _duplicates_generated_response_contract(source: str) -> set[str]:
    """Reject exported endpoint response shapes that are not OpenAPI-derived.

    BFF session DTOs and the documented audit screen projection are explicitly
    local. Every other exported *Response must point to a generated schema or
    an operation-success alias, preventing future names from bypassing a
    hand-maintained allowlist.
    """
    duplicates: set[str] = set()
    for interface in re.finditer(r"export\s+interface\s+(\w*Response)\b", source):
        name = interface.group(1)
        if name not in LOCAL_RESPONSE_TYPES:
            duplicates.add(name)
    for type_alias in re.finditer(
        r"export\s+type\s+(\w*Response)\s*=\s*([^;]+);", source
    ):
        name, value = type_alias.groups()
        if name in LOCAL_RESPONSE_TYPES | OPENAPI_FACADE_RESPONSE_TYPES:
            continue
        if not re.match(r"(?:BackendSchemas\[|BackendSuccessResponse<)", value.strip()):
            duplicates.add(name)
    return duplicates


def main() -> int:
    violations: list[str] = []
    referenced_operations: dict[str, set[str]] = {}
    duplicated: set[str] = set()
    for path in _spa_sources():
        if path == TRANSPORT or path in SERVER_SIDE_BFF_PROXY_MODULES:
            continue
        source = path.read_text(encoding="utf-8")
        # `fetch`, `globalThis.fetch`, optional calls, and aliases all contain
        # this token. Remove only literal BFF session calls; all other browser
        # fetch access must stay inside http.ts.
        source_without_session_fetches = BFF_SESSION_FETCH.sub("", source)
        if FETCH_REFERENCE.search(
            source_without_session_fetches
        ) or BRACKET_FETCH_REFERENCE.search(source_without_session_fetches):
            violations.append(_display_path(path))

    for path in _api_sources():
        if path == TRANSPORT:
            continue
        source = path.read_text(encoding="utf-8")
        if LEGACY_BACKEND_FETCH.search(source):
            violations.append(_display_path(path))
        operations = set(OPERATION_REFERENCE.findall(source))
        if operations:
            referenced_operations[_display_path(path)] = operations
        duplicated.update(_duplicates_generated_response_contract(source))
    if violations:
        print("[FAIL] SPA backend calls must use an operation-typed helper:")
        print("\n".join(violations))
        return 1
    allowed_operations = _bff_operation_ids()
    disallowed_operations = sorted(
        f"{path}: {operation}"
        for path, operations in referenced_operations.items()
        for operation in operations - allowed_operations
    )
    if disallowed_operations:
        print("[FAIL] SPA operations must be exposed by the BFF policy:")
        print("\n".join(disallowed_operations))
        return 1
    if duplicated:
        print("[FAIL] Generated backend response contracts must not be duplicated:")
        print("\n".join(sorted(duplicated)))
        return 1
    print("[PASS] SPA backend calls use the centralized contract boundary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
