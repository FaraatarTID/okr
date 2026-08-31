# Backend API and Worker (`backend_app`)

Documentation HQ: [README](../README.md)

`backend_app/` owns the deployable FastAPI transport layer and asynchronous
worker lifecycle for the enterprise OKR platform.

Boundary ownership:
- `main.py` and `routers/` own HTTP routes, request/response validation, and
  transport-level authorization orchestration.
- `jobs.py`, `job_runner.py`, and `worker.py` own durable job state and worker
  execution.
- `src/domain/` owns pure business rules; `src/services/` owns application use
  cases and external integrations.
- `src/database.py`, `src/models.py`, and `alembic/` own persistence concerns.

Dependency direction:

```text
spa-web -> spa-bff -> backend_app -> src/services -> src/domain
                                      |
                                      v
                                  persistence
```

Keep business behavior out of route handlers and keep frontend concerns out of
the backend. Add or update boundary coverage when introducing a new import
between service areas.
