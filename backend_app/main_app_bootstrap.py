"""Bootstrap helpers for main FastAPI app construction."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend_app.main_bootstrap_helpers import make_main_lifespan, register_main_routers
from backend_app.observability_http import install_observability_handlers


def build_main_app(
    *,
    logger: Any,
    main_module,
    is_supabase_api_mode_enabled,
    ensure_supabase_api_ready,
    init_database,
    ensure_admin_exists,
) -> FastAPI:
    """Create and configure the application instance used by the entry module."""

    lifespan = make_main_lifespan(
        is_supabase_api_mode_enabled=is_supabase_api_mode_enabled,
        ensure_supabase_api_ready=ensure_supabase_api_ready,
        init_database=init_database,
        ensure_admin_exists=ensure_admin_exists,
    )

    app = FastAPI(
        title="OKR Internal Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    install_observability_handlers(app, logger)
    register_main_routers(app=app, main_module=main_module)
    return app
