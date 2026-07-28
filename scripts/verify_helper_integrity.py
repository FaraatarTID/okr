#!/usr/bin/env python3
"""Verify helper-definition delegation and export-surface hygiene."""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("OKR_ENFORCE_ROUTE_BOOTSTRAP_ASSERT", "0")

TARGETS: dict[Path, list[str]] = {
    ROOT / "backend_app" / "main.py": [
        "_resolve_actor_scope",
        "_resolve_scope_for_actor",
        "_resolve_effective_cycle_id_for_scope",
        "_require_admin_actor_scope",
        "_require_admin_or_manager_actor_scope",
        "_coerce_owner_ids",
        "_coerce_string_list",
        "_read_query_payload",
    ],
    ROOT / "src" / "crud.py": [],
    ROOT / "backend_app" / "main_bootstrap_helpers.py": [],
    ROOT / "backend_app" / "main_runtime_helpers.py": [],
    ROOT / "backend_app" / "main_workflow_handlers.py": [],
    ROOT / "backend_app" / "main_mutation_handlers.py": [],
    ROOT / "src" / "crud_auth_helpers.py": [],
    ROOT / "src" / "crud_runtime_helpers.py": [],
}


EXPECTED_CALLABLE_SIGNATURES: dict[Path, dict[str, list[str]]] = {
    ROOT / "backend_app" / "main.py": {
        "_resolve_actor_scope": ["session", "actor_username", "token_version"],
        "_resolve_scope_for_actor": ["actor", "token_version"],
        "_resolve_effective_cycle_id_for_scope": ["scope", "requested_cycle_id", "required"],
        "_require_admin_actor_scope": ["actor"],
        "_require_admin_or_manager_actor_scope": ["actor"],
        "_coerce_owner_ids": ["values"],
        "_coerce_string_list": ["values"],
        "_read_query_payload": ["kind", "params", "actor"],
        "_atomic_idempotent_check": ["session", "actor", "scope_id", "payload"],
        "_complete_idempotent_response": ["actor", "response_payload", "status_code"],
        "create_app": [],
    },
    ROOT / "backend_app" / "main_bootstrap_helpers.py": {
        "make_main_lifespan": [
            "is_supabase_api_mode_enabled",
            "ensure_supabase_api_ready",
            "init_database",
            "ensure_admin_exists",
        ],
        "register_main_routers": ["app", "main_module"],
    },
    ROOT / "backend_app" / "main_runtime_helpers.py": {
        "_resolve_actor_scope": ["session", "actor_username", "token_version"],
        "_resolve_scope_for_actor": ["actor", "token_version"],
        "_resolve_effective_cycle_id_for_scope": ["scope", "requested_cycle_id", "required"],
        "_coerce_owner_ids": ["values"],
        "_coerce_string_list": ["values"],
        "_load_idempotent_response": ["scope", "actor", "idempotency_key", "payload"],
        "_store_idempotent_response": ["scope", "actor", "idempotency_key", "payload", "response_payload"],
        "_atomic_idempotent_check": ["scope", "actor", "idempotency_key", "payload"],
        "_complete_idempotent_response": ["scope", "actor", "idempotency_key", "response_payload"],
        "_payload_fingerprint": ["payload"],
        "_idempotency_state_key": ["scope", "actor", "key"],
        "get_observability_metrics_snapshot": [],
    },
    ROOT / "backend_app" / "main_mutation_handlers.py": {},
    ROOT / "backend_app" / "main_workflow_handlers.py": {},
    ROOT / "src" / "crud_auth_helpers.py": {
        "authenticate_user_detailed": ["username", "password", "client_ip"],
        "authenticate_user": ["username", "password", "client_ip"],
    },
    ROOT / "src" / "crud_runtime_helpers.py": {
        "hash_password": ["password"],
        "verify_password": ["password", "password_hash"],
        "get_user_by_username": ["username"],
    },
    ROOT / "src" / "crud.py": {},
}


@dataclass
class FileQuality:
    path: Path
    duplicate_defs: list[str]
    duplicate_all: list[str]
    non_wrapper_defs: list[str]
    missing_wrappers: list[str]


def _load_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _iter_top_level_names(tree: ast.Module) -> tuple[list[str], list[str]]:
    defs: list[str] = []
    dups: list[str] = []
    seen = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if name in seen:
                dups.append(name)
            seen.add(name)
            defs.append(name)
    return defs, dups


def _module_name_from_path(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def _extract_all_names(tree: ast.Module) -> list[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except Exception:
                return []
            if isinstance(value, list):
                return [item for item in value if isinstance(item, str)]
            return []
    return []


def _is_wrapper_function(tree: ast.Module, function_name: str) -> bool:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            body = [stmt for stmt in node.body if not isinstance(stmt, ast.Expr)]
            if len(body) != 1 or not isinstance(body[0], ast.Return):
                return False
            ret = body[0].value
            return isinstance(ret, ast.Call)
    return False


def _validate_runtime_signatures(path: Path, module_obj: object, expected_calls: dict[str, list[str]]) -> list[str]:
    issues: list[str] = []
    for symbol, expected_params in expected_calls.items():
        if not hasattr(module_obj, symbol):
            issues.append(f"{path.name}: expected exported symbol '{symbol}' is missing in runtime import check")
            continue

        symbol_value = getattr(module_obj, symbol)
        if not expected_params:
            continue
        if not callable(symbol_value):
            issues.append(f"{path.name}: expected exported symbol '{symbol}' should be callable for signature check")
            continue

        try:
            sig = inspect.signature(symbol_value)
        except (TypeError, ValueError) as exc:
            issues.append(
                f"{path.name}: unable to inspect signature for symbol '{symbol}': {exc}"
            )
            continue

        actual_params = [param.name for param in sig.parameters.values()]
        if expected_params != actual_params:
            issues.append(
                f"{path.name}: signature mismatch for '{symbol}': expected {expected_params}, got {actual_params}"
            )
    return issues


def verify_exports_and_duplicates(
    path: Path, required_wrappers: list[str]
) -> FileQuality:
    tree = _load_ast(path)
    defs, duplicate_defs = _iter_top_level_names(tree)
    defs_set = set(defs)

    all_names = _extract_all_names(tree)
    duplicate_all: list[str] = []
    seen_all = set()
    for name in all_names:
        if name in seen_all:
            duplicate_all.append(name)
        seen_all.add(name)

    non_wrapper_defs = [
        name for name in required_wrappers if name in defs_set and not _is_wrapper_function(tree, name)
    ]
    missing_wrappers = [name for name in required_wrappers if name not in defs_set]

    return FileQuality(
        path=path,
        duplicate_defs=duplicate_defs,
        duplicate_all=duplicate_all,
        non_wrapper_defs=non_wrapper_defs,
        missing_wrappers=missing_wrappers,
    )


def check() -> int:
    issues: list[str] = []
    for path, required_wrappers in TARGETS.items():
        quality = verify_exports_and_duplicates(path, required_wrappers)
        issues.extend([f"{path.name}: duplicate definition '{name}'" for name in quality.duplicate_defs])
        issues.extend([f"{path.name}: duplicate __all__ entry '{name}'" for name in quality.duplicate_all])
        issues.extend(
            [f"{path.name}: helper wrapper '{name}' is not a thin delegation function" for name in quality.non_wrapper_defs]
        )
        issues.extend([f"{path.name}: expected helper wrapper '{name}' is missing" for name in quality.missing_wrappers])

        module_name = _module_name_from_path(path)
        try:
            module_obj = importlib.import_module(module_name)
        except Exception as exc:
            issues.append(f"{path.name}: runtime import failed ({module_name}): {exc}")
            continue

        issues.extend(
            _validate_runtime_signatures(path, module_obj, EXPECTED_CALLABLE_SIGNATURES.get(path, {}))
        )

    if issues:
        for issue in issues:
            print(f"[INTEGRITY] {issue}")
        return 1

    print("[PASS] Helper integrity checks passed for targeted modules")
    return 0


def main() -> int:
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
