"""Bootstrap helpers for main FastAPI app construction."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend_app.body_limit import RouteBodyLimitMiddleware
from backend_app.main_bootstrap_helpers import make_main_lifespan, register_main_routers
from backend_app.observability_http import install_observability_handlers


def build_main_app(
    *,
    logger: Any,
    main_module,
    init_database,
    ensure_admin_exists,
    validate_runtime_preflight=None,
) -> FastAPI:
    """Create and configure the application instance used by the entry module."""

    lifespan = make_main_lifespan(
        init_database=init_database,
        ensure_admin_exists=ensure_admin_exists,
        validate_runtime_preflight=validate_runtime_preflight,
    )

    app = FastAPI(
        title="OKR Internal Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    install_observability_handlers(app, logger)
    # Added after the observability middleware so it is the outermost layer: the body
    # ceiling must apply before anything downstream reads the request.
    app.add_middleware(RouteBodyLimitMiddleware)
    register_main_routers(app=app, main_module=main_module)
    return app
