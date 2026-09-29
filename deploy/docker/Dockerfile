FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

COPY --from=ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 /uv /uvx /bin/

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      fonts-dejavu; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock /app/
# Playwright (the `browser` dependency group) is left out of the runtime image: 138 MB of
# site-packages and no Chromium binary, so PDF_METHOD=chromium cannot render from this image
# either way. Build with --build-arg INSTALL_BROWSER_GROUP=true to add the package; a browser
# binary (OKR_CHROMIUM_EXECUTABLE_PATH) is still the operator's to provide.
ARG INSTALL_BROWSER_GROUP=false
RUN set -eux; \
    if [ "$INSTALL_BROWSER_GROUP" = "true" ]; then extra="--group browser"; else extra=""; fi; \
    uv sync --frozen --no-dev --no-install-project $extra
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ /app/src/
COPY backend_app/ /app/backend_app/
COPY scripts/seed_dev_demo.py /app/scripts/seed_dev_demo.py
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/

RUN useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

COPY deploy/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && chown appuser:appuser /entrypoint.sh

EXPOSE 8100
ENV PORT=8100

USER appuser
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "backend_app.run_api"]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:${PORT}/healthz || exit 1
