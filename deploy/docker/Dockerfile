# Production container for OKR Streamlit app
FROM python:3.11-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (wkhtmltopdf is needed by pdfkit)
RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         wkhtmltopdf \
         fonts-dejavu \
         ca-certificates \
         curl \
     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy app source
COPY streamlit_app/ /app/streamlit_app/

# Install Python deps
RUN python -m pip install --upgrade pip \
    && pip install -r /app/streamlit_app/requirements.txt

# Create non-root user
RUN useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

# Persist database and any generated files under /data
VOLUME ["/data"]

# Add entrypoint for DB persistence/linking
COPY deploy/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && chown appuser:appuser /entrypoint.sh

EXPOSE 8501

ENV PORT=8501
ENV BASE_URL_PATH=""

# Streamlit must run from the project folder (alembic.ini is here)
WORKDIR /app/streamlit_app

USER appuser
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT} ${BASE_URL_PATH:+--server.baseUrlPath=${BASE_URL_PATH}} --browser.gatherUsageStats false"]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:${PORT}/ || exit 1
