Documentation HQ: [README](../README.md)

# Alpha Test Profiles

This app is an enterprise OKR system currently in **alpha testing** on a personal
PC (backend + SPA + worker) with a Supabase free-tier database. Two configuration
profiles are supported and both should be exercised during alpha.

## Profile 1: Local-Relaxed (developer/onboarding path)

Validates the low-friction local setup a new developer or tester would use.

```bat
set OKR_ENV=development
set OKR_BACKEND_HOST=127.0.0.1
set OKR_BACKEND_SERVICE_TOKEN=<random-token>
rem Security state stays in memory (default in non-production)
set AI_PROVIDER=jan
set AI_BASE_URL=http://127.0.0.1:1337/v1
set AI_MODEL=<model-loaded-in-Jan>
rem Database: either Supabase direct, or SQLite for offline trials:
set OKR_DATABASE_URL=sqlite:///./tmp/okr-alpha.db
```

Or simply run `run_hybrid_app_local.bat`, which already sets the loopback host.

## Profile 2: Enterprise-Parity (production rehearsal)

Exercises what production will actually do: DB-backed security state, token +
HMAC request signing enforced, Supabase pooler, remote AI provider.

```bat
set OKR_ENV=production
set OKR_BACKEND_HOST=0.0.0.0
set OKR_BACKEND_SERVICE_TOKEN=<random-token>
set OKR_BACKEND_SIGNING_SECRET=<random-secret>
set OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true
set OKR_BACKEND_SECURITY_STATE_BACKEND=database
set OKR_DATABASE_URL=<supabase-pooler-url>
set OKR_ALLOW_SUPABASE_SESSION_POOLER=true
set ALLOW_EXTERNAL_AI=true
set AI_PROVIDER=gemini
set GEMINI_API_KEY=<key>
```

## Alpha Test Checklist

1. Run both profiles; confirm login, Atlas load, KR updates, PDF weekly job,
   and AI JSON generation work in each.
2. Compare Jan (local) vs Gemini (remote) output quality/shape for the same
   prompts — provider parity is an explicit alpha item.
3. Treat these as **known environment limits**, not bugs:
   - Supabase free tier pauses after inactivity → first requests may fail until
     the database resumes.
   - Pooler connection drops may surface as 503 from the fail-closed security
     state store.
   - Row limits if audit-event retention grows — keep pruning enabled.
4. Rehearse `alembic upgrade head` against a Supabase-shaped database before
   real users exist.
5. Keep `OKR_BACKEND_HOST=127.0.0.1` unless deliberately testing LAN access;
   `0.0.0.0` exposes the API to the whole network.
