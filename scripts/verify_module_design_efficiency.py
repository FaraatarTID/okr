#!/usr/bin/env python3
"""Design/efficiency gate for facade modules and ownership seams.

This gate evaluates: ownership clarity, wrapper thinness, and seam stability
without relying on a fixed line-length threshold.
"""

from __future__ import annotations

import ast
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class ModuleProfile:
    module_name: str
    path: Path
    total_defs: int
    total_assignments: int
    thin_wrapper_count: int
    required_symbol_missing: list[str]
    non_wrapper_required: list[str]
    high_complexity_defs: list[str]
    forbidden_pattern_hits: list[str]
    import_coverage_ok: bool
    module_is_facade_like: bool


def _is_thin_wrapper(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [stmt for stmt in func.body if not isinstance(stmt, ast.Expr)]
    if len(body) != 1:
        return False
    ret = body[0]
    if not isinstance(ret, ast.Return):
        return False
    val = ret.value
    if val is None:
        return False
    return isinstance(val, ast.Call)


def _cyclomatic_approx(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
                ast.IfExp,
            ),
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            if len(child.values) > 1:
                complexity += len(child.values) - 1
        elif isinstance(child, (ast.And, ast.Or)):
            complexity += 1
    return complexity


def _string_contains_any(text: str, patterns: list[str]) -> list[str]:
    lowered = text.lower()
    return [pat for pat in patterns if pat in lowered]


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_module_imports(tree: ast.AST, expected_prefixes: list[str]) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            full_module = node.module
            if any(full_module.startswith(prefix) for prefix in expected_prefixes):
                return True
            for alias in node.names:
                candidate = f"{full_module}.{alias.name}"
                if any(candidate.startswith(prefix) for prefix in expected_prefixes):
                    return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(prefix) for prefix in expected_prefixes):
                    return True
                if alias.name == "src":
                    if any(f"src.{alias.name}".startswith(prefix) for prefix in expected_prefixes):
                        return True
    return False


def _profile_module(path: Path, expected: dict[str, object]) -> ModuleProfile:
    source = _read_file(path)
    tree = ast.parse(source)

    required = expected["required"]
    required_wrappers: list[str] = expected["required_thin_wrappers"]
    imports_required: list[str] = expected["required_seams"]
    forbid: list[str] = expected["forbidden_patterns"]
    max_complexity: int = expected["max_complexity"]
    max_defs: int = expected["max_defs"]

    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    required_missing: list[str] = []
    high_complexity: list[str] = []
    non_wrapper_required: list[str] = []
    thin_wrapper_count = 0

    for fn in defs:
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = _cyclomatic_approx(fn)
            if complexity > max_complexity:
                high_complexity.append(f"{fn.name} (complexity={complexity})")
            if _is_thin_wrapper(fn):
                thin_wrapper_count += 1
            elif fn.name in required_wrappers:
                non_wrapper_required.append(fn.name)

    # Module-level symbol-level checks by importable module contract.
    try:
        module_obj = importlib.import_module(expected["module"])
    except Exception as exc:
        required_missing.extend(required)
        return ModuleProfile(
            module_name=expected["module"],
            path=path,
            total_defs=len(defs),
            total_assignments=sum(1 for node in tree.body if isinstance(node, ast.Assign)),
            thin_wrapper_count=thin_wrapper_count,
            required_symbol_missing=required_missing,
            non_wrapper_required=non_wrapper_required,
            high_complexity_defs=high_complexity,
            forbidden_pattern_hits=[f"module import failed: {exc}"],
            import_coverage_ok=False,
            module_is_facade_like=len(defs) <= max_defs,
        )

    for symbol in required:
        if not hasattr(module_obj, symbol):
            required_missing.append(symbol)

    forbidden_hits = _string_contains_any(source, forbid)

    return ModuleProfile(
        module_name=expected["module"],
        path=path,
        total_defs=len(defs),
        total_assignments=sum(1 for node in tree.body if isinstance(node, ast.Assign)),
        thin_wrapper_count=thin_wrapper_count,
        required_symbol_missing=required_missing,
        non_wrapper_required=non_wrapper_required,
        high_complexity_defs=high_complexity,
        forbidden_pattern_hits=forbidden_hits,
        import_coverage_ok=_contains_module_imports(tree, imports_required),
        module_is_facade_like=len(defs) <= max_defs,
    )


def run_checks() -> int:
    module_specs = {
        "backend_app.main": {
            "module": "backend_app.main",
            "path": "backend_app/main.py",
            "required": [
                "app",
                "create_app",
                "api_create_goal",
                "api_create_objective",
                "api_create_key_result",
                "api_create_task",
                "api_update_node",
                "api_delete_node",
                "api_delete_team",
                "api_create_alignment",
                "api_update_experiment",
                "api_create_retrospective",
                "authenticate_user_detailed",
                "get_leadership_metrics",
                "get_observability_metrics_snapshot",
                "_read_query_payload",
            ],
            "required_thin_wrappers": [
                "_resolve_actor_scope",
                "_resolve_scope_for_actor",
                "_resolve_effective_cycle_id_for_scope",
                "_require_admin_actor_scope",
                "_require_admin_or_manager_actor_scope",
                "_coerce_owner_ids",
                "_coerce_string_list",
                "_atomic_idempotent_check",
                "_complete_idempotent_response",
                "_load_idempotent_response",
                "_store_idempotent_response",
                "_read_query_payload",
            ],
            "required_seams": [
                "backend_app.main_bootstrap_helpers",
                "backend_app.main_runtime_helpers",
                "backend_app.main_mutation_handlers",
                "backend_app.main_workflow_handlers",
                "backend_app.main_helpers",
                "backend_app.scope_resolution",
                "backend_app.read_query_helpers",
            ],
            "forbidden_patterns": [
                "session.query",
                "session.commit",
                "session.execute",
                "Session(",
                "select(",
                "with session",
                "await get_session_context",
            ],
            "max_complexity": 5,
            "max_defs": 20,
        },
        "src.crud.py": {
            "module": "src.crud",
            "path": "src/crud.py",
            "required": [
                "get_user_by_id",
                "create_goal",
                "create_team",
                "start_timer",
                "authenticate_user_detailed",
                "_backend_mutation_proxy_enabled",
                "_backend_read_proxy_enabled",
                "calculate_progress",
                "create_retrospective",
                "get_active_cycles",
            ],
            "required_thin_wrappers": [],
            "required_seams": [
                "src.crud_runtime_helpers",
                "src.crud_auth_helpers",
                "src.crud_read_facade",
                "src.crud_mutation_facade",
                "src.crud_timer_facade",
            ],
            "forbidden_patterns": [
                "session.",
                "Session(",
                "select(",
                "commit()",
                "rollback()",
            ],
            "max_complexity": 1,
            "max_defs": 0,
        },
        "src.services.supabase_api_mode.py": {
            "module": "src.services.supabase_api_mode",
            "path": "src/services/supabase_api_mode.py",
            "required": [
                "create_goal_via_supabase_api",
                "create_objective_via_supabase_api",
                "create_key_result_via_supabase_api",
                "create_task_via_supabase_api",
                "update_node_via_supabase_api",
                "delete_node_via_supabase_api",
                "is_supabase_api_mode_enabled",
                "ensure_supabase_api_ready",
                "_base_url",
                "_api_key",
                "_request_json",
            ],
            "required_thin_wrappers": [],
            "required_seams": [
                "src.services.supabase_api_mode_atlas",
                "src.services.supabase_api_mode_read",
                "src.services.supabase_api_mode_mutation",
                "src.services.supabase_api_mode_nodes",
                "src.services.supabase_api_mode_operations",
                "src.services.supabase_api_mode_transport",
            ],
            "forbidden_patterns": [
                " import psycopg2",
                "import sqlmodel",
                "session.",
                "requests.request(",
            ],
            "max_complexity": 1,
            "max_defs": 0,
        },
    }

    issues: list[str] = []
    for conf in module_specs.values():
        module_path = ROOT / conf["path"]
        profile = _profile_module(module_path, conf)

        print(
            f"[DESIGN] {profile.module_name}: "
            f"defs={profile.total_defs} "
            f"assignments={profile.total_assignments} "
            f"thin_wrappers={profile.thin_wrapper_count}"
        )

        if profile.forbidden_pattern_hits:
            issues.append(
                f"{profile.module_name}: forbidden patterns detected -> {', '.join(sorted(set(profile.forbidden_pattern_hits)))}"
            )
        if profile.required_symbol_missing:
            issues.append(
                f"{profile.module_name}: missing required symbols -> {', '.join(sorted(profile.required_symbol_missing))}"
            )
        if profile.non_wrapper_required:
            issues.append(
                f"{profile.module_name}: required wrappers are not thin delegation -> {', '.join(sorted(profile.non_wrapper_required))}"
            )
        if profile.high_complexity_defs:
            issues.append(
                f"{profile.module_name}: high-complexity definitions -> {', '.join(profile.high_complexity_defs)}"
            )
        if not profile.import_coverage_ok:
            issues.append(f"{profile.module_name}: helper-seam imports not detected")
        if not profile.module_is_facade_like:
            issues.append(
                f"{profile.module_name}: function/class count exceeds facade profile budget ({profile.total_defs})"
            )

        if profile.module_name == "backend_app.main" and profile.thin_wrapper_count < 6:
            issues.append("backend_app.main: thin-wrapper count unexpectedly low for facade compatibility surface")

    if issues:
        for issue in issues:
            print(f"[DESIGN-FAIL] {issue}")
        return 1

    print("[PASS] Module design/efficiency gate passed")
    return 0


def main() -> int:
    return run_checks()


if __name__ == "__main__":
    raise SystemExit(main())
