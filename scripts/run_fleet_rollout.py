"""Lease and execute one bounded batch of tenant migrations from the control plane.

Database URLs are read from a short-lived secure mapping supplied by the runner;
they are never inserted into the control-plane database or its reports.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.migrate_tenant_databases import _default_runner
from src.saas.fleet_control_plane import SqlControlPlane


def run_batch(
    plane: SqlControlPlane,
    rollout_id: int,
    owner: str,
    database_urls: dict[str, str],
    *,
    max_concurrency: int = 10,
    timeout_seconds: float = 300.0,
    max_retries: int = 1,
    retry_backoff_seconds: float = 2.0,
    incident_reference: str | None = None,
    health_check: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    tasks = plane.lease_tasks(rollout_id, owner, limit=max_concurrency)

    def execute(task: dict[str, Any]) -> tuple[int, str | None, str | None, int]:
        resource = plane.database_resource_for(task["environment_id"])
        url = database_urls.get(resource)
        if not url:
            return int(task["id"]), None, "no database URL for opaque resource", 1
        revision: str | None = None
        error: str | None = None
        attempts = 0
        for attempt in range(max_retries + 1):
            attempts = attempt + 1
            revision, error = _default_runner(
                database_url=url,
                timeout_seconds=timeout_seconds,
                lock_id=task["environment_id"],
            )
            if error is None:
                break
            if attempt < max_retries:
                time.sleep(retry_backoff_seconds * (2**attempt))
        if (
            error is None
            and health_check is not None
            and not health_check(task["environment_id"])
        ):
            return (
                int(task["id"]),
                revision,
                "post-migration health check failed",
                attempts,
            )
        return int(task["id"]), revision, error, attempts

    with ThreadPoolExecutor(max_workers=min(max_concurrency, len(tasks) or 1)) as pool:
        futures = [pool.submit(execute, task) for task in tasks]
        for future in as_completed(futures):
            task_id, revision, error, attempts = future.result()
            plane.complete_task(
                task_id, owner, revision=revision, error=error, attempts=attempts
            )
            if incident_reference:
                plane.record_audit(
                    next(
                        task["environment_id"]
                        for task in tasks
                        if task["id"] == task_id
                    ),
                    "MIGRATION_BATCH_RESULT",
                    owner,
                    {
                        "rollout_id": rollout_id,
                        "incident_reference": incident_reference,
                        "revision": revision,
                        "error": error,
                        "attempts": attempts,
                    },
                )
    status = plane.status(rollout_id)
    return {"leased": len(tasks), **status}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-plane-url", required=True)
    parser.add_argument("--rollout-id", type=int, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--database-urls-file", type=Path, required=True)
    parser.add_argument(
        "--health-urls-file",
        type=Path,
        required=True,
        help="JSON mapping of environment ID to internal health URL.",
    )
    parser.add_argument("--max-concurrency", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--incident-reference", required=True)
    args = parser.parse_args(argv)
    if args.max_concurrency not in range(1, 11):
        parser.error("--max-concurrency must be between 1 and 10")
    if args.max_retries < 0 or args.retry_backoff_seconds < 0:
        parser.error("retry values must be non-negative")
    urls = json.loads(args.database_urls_file.read_text(encoding="utf-8"))
    health_urls = json.loads(args.health_urls_file.read_text(encoding="utf-8"))

    def health_check(environment_id: str) -> bool:
        url = health_urls.get(environment_id)
        if not url:
            return False
        try:
            return httpx.get(url, timeout=args.timeout_seconds).is_success
        except httpx.HTTPError:
            return False

    plane = SqlControlPlane(args.control_plane_url)
    result = run_batch(
        plane,
        args.rollout_id,
        args.owner,
        urls,
        max_concurrency=args.max_concurrency,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        incident_reference=args.incident_reference,
        health_check=health_check,
    )
    print(json.dumps(result, sort_keys=True))
    return 1 if result["state"] == "halted" else 0


if __name__ == "__main__":
    raise SystemExit(main())
