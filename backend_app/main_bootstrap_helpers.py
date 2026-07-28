"""Bootstrap helpers for `backend_app.main` app initialization."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Callable

from fastapi import APIRouter, FastAPI


_REQUIRED_MUTATION_ROUTES = {
    ("POST", "/v1/nodes/goal"),
}


def make_main_lifespan(
    *,
    is_supabase_api_mode_enabled: Callable[[], bool],
    ensure_supabase_api_ready: Callable[[], None],
    init_database: Callable[[], None],
    ensure_admin_exists: Callable[[], None],
):
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        if is_supabase_api_mode_enabled():
            ensure_supabase_api_ready()
        else:
            init_database()
            # Hybrid SPA startup relies on bootstrap admin seed for fresh local DB.
            ensure_admin_exists()
        yield

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
    if os.getenv("OKR_SKIP_ROUTE_BOOTSTRAP_ASSERT", "").strip().lower() in {"1", "true", "yes"}:
        return

    available = set()
    for route in app.routes:
        if getattr(route, "path", None) is None or getattr(route, "methods", None) is None:
            continue
        methods = set(route.methods or set())
        for method in methods:
            available.add((method, _normalize_route_path(route.path)))

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
