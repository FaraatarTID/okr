"""Entrypoint helper for running backend API with uvicorn."""

from __future__ import annotations

import uvicorn

from backend_app.config import get_backend_settings


def main() -> None:
    settings = get_backend_settings()
    uvicorn.run(
        "backend_app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
