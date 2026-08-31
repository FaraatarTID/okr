import asyncio

import pytest
from fastapi import FastAPI

from backend_app.main_bootstrap_helpers import make_main_lifespan


def test_backend_boot_fails_when_runtime_preflight_rejects_saas_mode():
    def reject_invalid_configuration():
        raise RuntimeError("SaaS deployment profile permits only database")

    lifespan = make_main_lifespan(
        is_supabase_api_mode_enabled=lambda: False,
        ensure_supabase_api_ready=lambda: None,
        init_database=lambda: None,
        ensure_admin_exists=lambda: None,
        validate_runtime_preflight=reject_invalid_configuration,
    )

    async def start_app():
        async with lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="only database"):
        asyncio.run(start_app())
