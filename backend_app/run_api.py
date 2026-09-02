"""Entrypoint helper for running backend API with uvicorn."""

from __future__ import annotations

import uvicorn

from backend_app.config import get_backend_settings


def main() -> None:
    from backend_app.path_setup import ensure_shared_src_on_path

    ensure_shared_src_on_path()

    settings = get_backend_settings()
    uvicorn.run(
        "backend_app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        workers=settings.api_workers,
    )


if __name__ == "__main__":
    main()
