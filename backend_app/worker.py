"""DB-backed async worker for AI/PDF backend jobs."""

from __future__ import annotations

import time
import traceback

from backend_app.config import get_backend_settings
from backend_app.job_runner import run_job
from backend_app.jobs import (
    claim_next_pending_job,
    get_job,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_succeeded,
)
from backend_app.path_setup import ensure_streamlit_app_on_path

ensure_streamlit_app_on_path()

from src.database import init_database


def process_next_job(*, worker_id: str) -> bool:
    job = claim_next_pending_job(worker_id)
    if not job:
        return False

    try:
        payload = {}
        if job.payload_json:
            import json

            parsed = json.loads(job.payload_json)
            if isinstance(parsed, dict):
                payload = parsed

        result = run_job(str(job.kind), payload)

        latest = get_job(job.id)
        if latest and bool(latest.cancel_requested):
            mark_job_cancelled(job.id, error_text="Cancelled while running.")
        else:
            mark_job_succeeded(job.id, result)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        trace = traceback.format_exc(limit=3)
        mark_job_failed(job.id, f"{msg}\n{trace}")
    return True


def run_worker_loop() -> None:
    settings = get_backend_settings()
    worker_id = f"backend-worker-{int(time.time())}"
    init_database()
    print(f"Worker started ({worker_id})")
    while True:
        handled = process_next_job(worker_id=worker_id)
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run_worker_loop()
