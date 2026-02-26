FROM python:3.11-slim

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

COPY backend_app/requirements.txt /app/backend_app/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /app/backend_app/requirements.txt

COPY src/ /app/src/
COPY backend_app/ /app/backend_app/
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
