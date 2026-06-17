Documentation HQ: [README](README.md)

# Streamlit Cloud Deployment Guide

## Overview

This app uses a **backend-first architecture**: the Streamlit UI communicates
with a FastAPI backend for all data mutations. On Streamlit Cloud, the backend
runs **in the same container** as the frontend (embedded mode).

Status:

- Embedded mode is implemented and currently operational on Streamlit Cloud.
- This mode exists for compatibility and demo/MVP hosting.
- Corporate production deployments should use the decoupled backend-server architecture documented in [DEPLOYMENT.md](DEPLOYMENT.md).

## How It Works on Streamlit Cloud

When the app starts, it automatically launches the FastAPI backend as a
background process if one of these conditions is true:

| Condition                                       | Action                              |
| ----------------------------------------------- | ----------------------------------- |
| `OKR_BACKEND_API_URL = "auto"`                  | Always start the embedded backend   |
| `OKR_BACKEND_API_URL` is empty                  | Start embedded backend (cloud only) |
| `OKR_BACKEND_API_URL = "http://localhost:8100"` | Start embedded backend (cloud only) |

---

## Step-by-Step Setup

### 1. Fork & Connect the Repository

Connect your GitHub repository to Streamlit Cloud as normal. Set the
**main file path** to: `streamlit_app/app.py`

### 2. Configure Secrets

In your Streamlit Cloud app dashboard → **Settings → Secrets**, paste the
following, replacing all placeholder values:

```toml
# ── Backend URL (use 'auto' to start the embedded backend automatically) ──
OKR_BACKEND_API_URL = "auto"

# ── A shared secret that the frontend uses to authenticate with the backend ──
# Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
OKR_BACKEND_SERVICE_TOKEN = "your-random-secret-here"

# ── AI Integration (optional but recommended) ──
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "your-gemini-api-key"
ALLOW_EXTERNAL_AI = true

# ── PDF export (optional) ──
PDF_METHOD = "pdfshift"
pdfshift_api_key = "your-pdfshift-key"

# ── Database (required unless using default SQLite — see note below) ──
[database]
url = "postgresql+psycopg2://user:password@host:5432/dbname?sslmode=require"

# ── Security (recommended for production) ──
OKR_STRICT_RUNTIME_PREFLIGHT = true
```

> **Important:** Do NOT commit `secrets.toml` with real credentials to your
> repository. The `.gitignore` already excludes it. The secrets above are only
> configured via the Streamlit Cloud UI.

### 3. Database

The app requires a PostgreSQL database. Free options:

| Service                    | Notes                           |
| -------------------------- | ------------------------------- |
| **Supabase** (recommended) | Free tier, easy setup, Postgres |
| **Neon**                   | Serverless Postgres, free tier  |
| **ElephantSQL**            | Simple hosted Postgres          |

Set the connection string in the `[database]` section of your secrets.

### 4. Deploy

Click **Deploy** in Streamlit Cloud. The app will:

1. Install dependencies from `requirements.txt`
2. Start the Streamlit frontend
3. Automatically launch the FastAPI backend in the background
4. Wait up to 15 seconds for the backend to become ready

---

## Environment Variables Reference

| Variable                       | Required        | Default               | Description                                     |
| ------------------------------ | --------------- | --------------------- | ----------------------------------------------- |
| `OKR_BACKEND_API_URL`          | Yes (or `auto`) | —                     | Backend URL. Set to `"auto"` for embedded mode. |
| `OKR_BACKEND_SERVICE_TOKEN`    | Yes             | —                     | Shared secret for frontend→backend auth.        |
| `GEMINI_API_KEY`               | No              | —                     | Google Gemini API key for AI features.          |
| `OKR_STRICT_RUNTIME_PREFLIGHT` | No              | `true`                | Block app start if preflight checks fail.       |
| `OKR_BACKEND_PORT`             | No              | `8100`                | Port the embedded backend listens on.           |
| `OKR_ENV`                      | No              | `production` on cloud | Runtime environment name.                       |

---

## Troubleshooting

### "Backend read failed and local fallback is disabled"

The embedded backend failed to start within 15 seconds. Check:

- Your database URL is correct in secrets
- `OKR_BACKEND_SERVICE_TOKEN` is set
- View the app's **Manage app → Logs** for detailed error output

### App is very slow on first load

The embedded backend runs database migrations on startup (Alembic). This can
take 5–10 seconds on a cold start. Subsequent loads will be faster.

### "OKR_BACKEND_API_URL is required" error

Ensure you have configured secrets in the Streamlit Cloud dashboard (not just
in a local `secrets.toml` file that won't be deployed).

---

## Scaling Out (Beyond Streamlit Cloud)

If your user base grows and you need to scale horizontally (e.g., Kubernetes, AWS ECS, or multiple VMs), you should move **away** from "Embedded Mode" to a de-coupled architecture.

See the [Cluster Deployment & Horizontal Scaling](DEPLOYMENT.md#path-b-horizontal-cluster-scaling-kubernetes--ecs--nomad) section in the main deployment guide for:

- Splitting the app into Frontend, API, and Worker tiers.
- Architectural diagrams for high-availability clusters.
- Config requirements for shared state (Redis) and Sticky Sessions.
