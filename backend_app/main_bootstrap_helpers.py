"""Bootstrap helpers for `backend_app.main` app initialization."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from src.config_runtime import get_bool_config, get_config_value
from src.runtime_preflight import evaluate_runtime_preflight


_REQUIRED_MUTATION_ROUTES = {
    ("POST", "/v1/nodes/goal"),
}


def validate_runtime_preflight() -> None:
    """Fail fast on deployment settings that violate the runtime contract."""
    strict = get_bool_config("OKR_STRICT_RUNTIME_PREFLIGHT", default=True)
    profile = get_config_value("OKR_DEPLOYMENT_PROFILE", "")
    mode = get_config_value("OKR_DATA_ACCESS_MODE", "database")
    if not strict and str(profile).strip().lower() not in {"single_tenant_saas", "saas"}:
        return

    report = evaluate_runtime_preflight(
        pdf_method="chromium",
        has_pdfshift_key=True,
        has_chromium_runtime=True,
        external_ai_allowed=False,
        backend_api_url="auto",
        deployment_profile=profile,
        data_access_mode=mode,
    )
    if report.errors:
        raise RuntimeError(
            "Runtime preflight failed:\n"
            + "\n".join(f"- {error}" for error in report.errors)
        )


def make_main_lifespan(
    *,
    is_supabase_api_mode_enabled: Callable[[], bool],
    ensure_supabase_api_ready: Callable[[], None],
    init_database: Callable[[], None],
    ensure_admin_exists: Callable[[], None],
    validate_runtime_preflight: Callable[[], None] | None = None,
):
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        if validate_runtime_preflight is not None:
            validate_runtime_preflight()
        if is_supabase_api_mode_enabled():
            ensure_supabase_api_ready()
        else:
            init_database()
            # Hybrid SPA startup relies on bootstrap admin seed for fresh local DB.
            ensure_admin_exists()
        try:
            yield
        finally:
            # Release pooled Supabase HTTP connections on shutdown.
            from src.services.supabase_api_mode_transport import (
                shutdown_close_transport,
            )

            shutdown_close_transport()

    return _lifespan


def register_main_routers(*, app: FastAPI, main_module) -> None:
    from backend_app.routers.ai_routes import register_ai_routes
    from backend_app.routers.platform_routes import register_platform_routes
    from backend_app.routers.operations_routes import register_operations_routes
    from backend_app.routers.node_mutation_routes import register_node_mutation_routes
    from backend_app.routers.cycle_mutation_routes import register_cycle_mutation_routes
    from backend_app.routers.checkin_mutation_routes import (
        register_checkin_mutation_routes,
    )
    from backend_app.routers.team_mutation_routes import register_team_mutation_routes
    from backend_app.routers.experiment_mutation_routes import (
        register_experiment_mutation_routes,
    )
    from backend_app.routers.analytics_mutation_routes import (
        register_analytics_mutation_routes,
    )
    from backend_app.routers.user_mutation_routes import register_user_mutation_routes

    _platform_router = APIRouter()
    register_platform_routes(_platform_router, main_module)
    app.include_router(_platform_router)

    _operations_router = APIRouter()
    register_operations_routes(_operations_router, main_module)
    app.include_router(_operations_router)

    _ai_router = APIRouter()
    register_ai_routes(_ai_router, main_module)
    app.include_router(_ai_router)

    _node_mutation_router = APIRouter()
    register_node_mutation_routes(_node_mutation_router, main_module)
    app.include_router(_node_mutation_router)

    _user_mutation_router = APIRouter()
    register_user_mutation_routes(_user_mutation_router, main_module)
    app.include_router(_user_mutation_router)

    _checkin_mutation_router = APIRouter()
    register_checkin_mutation_routes(_checkin_mutation_router, main_module)
    app.include_router(_checkin_mutation_router)

    _cycle_mutation_router = APIRouter()
    register_cycle_mutation_routes(_cycle_mutation_router, main_module)
    app.include_router(_cycle_mutation_router)

    _team_mutation_router = APIRouter()
    register_team_mutation_routes(_team_mutation_router, main_module)
    app.include_router(_team_mutation_router)

    _experiment_mutation_router = APIRouter()
    register_experiment_mutation_routes(_experiment_mutation_router, main_module)
    app.include_router(_experiment_mutation_router)

    _analytics_mutation_router = APIRouter()
    register_analytics_mutation_routes(_analytics_mutation_router, main_module)
    app.include_router(_analytics_mutation_router)

    _assert_required_routes(app=app)


def _assert_required_routes(*, app: FastAPI) -> None:
    """
    Fail fast when a required mutation endpoint is missing from the router table.
    """
    available = set()

    def _collect(route_objects):
        for route in route_objects:
            if isinstance(route, APIRoute):
                methods = set(route.methods or set())
                for method in methods:
                    available.add((method, _normalize_route_path(route.path)))
                continue

            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                _collect(getattr(original_router, "routes", []))
                continue

            nested_routes = getattr(route, "routes", None)
            if nested_routes is not None:
                _collect(nested_routes)

    _collect(app.routes)

    for method, path in sorted(_REQUIRED_MUTATION_ROUTES):
        if (method, _normalize_route_path(path)) not in available:
            # Include a concise fallback that surfaces contract issues early.
            raise RuntimeError(
                f"Required route missing during bootstrap: {method} {path}"
            )


def _normalize_route_path(path: str) -> str:
    """Normalize route path for stable equality checks."""
    normalized = "/" + "/".join(segment for segment in (path or "").split("/") if segment)
    if normalized == "//":
        normalized = "/"
    return normalized
