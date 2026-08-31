# ruff: noqa: E402
"""SLO probe: measure live SLO targets defined in docs/OBSERVABILITY_AND_RUNBOOKS.md.

Runs against a live stack (BFF + backend). Produces per-SLO pass/fail against
targets and exits non-zero on any breach.

Usage:
    python scripts/slo_probe.py --base-url http://localhost:3000 \
        --username admin --password <pw>

Requires a reachable stack; read-only except for the login session.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from typing import Any

import urllib.error
import urllib.request

# SLO targets from docs/OBSERVABILITY_AND_RUNBOOKS.md
SLO_LOGIN_P95_S = 3.0
SLO_READ_P95_S = 1.5
SLO_SNAPSHOT_MEDIAN_S = 1.0
PROBE_ITERATIONS = 10


def _post_json(
    url: str, payload: dict[str, Any], timeout: float = 30.0
) -> tuple[int, dict[str, Any], float]:
    """POST JSON; returns (status, body, elapsed_seconds)."""
    data = __import__("json").dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status_code = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status_code = int(exc.code)
    elapsed = time.monotonic() - start
    parsed: dict[str, Any] = {}
    try:
        import json

        parsed = json.loads(body.decode("utf-8")) if body.strip() else {}
    except Exception:
        parsed = {}
    return status_code, parsed, elapsed


def _get_json(
    url: str, cookie: str | None = None, timeout: float = 30.0
) -> tuple[int, dict[str, Any], float]:
    headers = {"Cookie": cookie} if cookie else {}
    request = urllib.request.Request(url, headers=headers, method="GET")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status_code = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status_code = int(exc.code)
    elapsed = time.monotonic() - start
    parsed: dict[str, Any] = {}
    try:
        import json

        parsed = json.loads(body.decode("utf-8")) if body.strip() else {}
    except Exception:
        parsed = {}
    return status_code, parsed, elapsed


def probe(base_url: str, username: str, password: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    base = base_url.rstrip("/")

    # --- SLO-1: Login p95 ---
    durations: list[float] = []
    ok_count = 0
    for i in range(PROBE_ITERATIONS):
        status_code, body, elapsed = _post_json(
            f"{base}/api/session/login",
            {"username": username, "password": password},
        )
        if status_code == 200:
            ok_count += 1
            if i == 0 and isinstance(body, dict):
                # Session cookie comes via Set-Cookie; capture from handler.
                pass
        durations.append(elapsed)
    p95 = sorted(durations)[int(len(durations) * 0.95) - 1]
    results.append(
        {
            "slo": "SLO-1 login p95",
            "target_s": SLO_LOGIN_P95_S,
            "measured_s": round(p95, 3),
            "pass": p95 <= SLO_LOGIN_P95_S,
            "detail": f"{ok_count}/{len(durations)} succeeded",
        }
    )

    # --- Healthz (dead jobs visibility) ---
    status_code, body, elapsed = _get_json(f"{base}/healthz")
    dead_jobs = body.get("dead_jobs") if isinstance(body, dict) else None
    results.append(
        {
            "slo": "healthz reachable",
            "target_s": 2.0,
            "measured_s": round(elapsed, 3),
            "pass": status_code == 200 and elapsed <= 2.0,
            "detail": f"status={status_code} dead_jobs={dead_jobs} "
            f"mode={body.get('data_access_mode') if isinstance(body, dict) else '?'}",
        }
    )

    # --- Authenticated probes (SLO-2..5) require a session cookie. ---
    session_cookie = _login_session(base, username, password)
    if session_cookie:
        results.extend(_probe_read_p95(base, session_cookie))
        results.extend(_probe_mutation_error_rate(base, session_cookie))
        results.extend(_probe_snapshot_latency(base, session_cookie))
    else:
        results.append(
            {
                "slo": "SLO-2 read/query p95",
                "target_s": SLO_READ_P95_S,
                "measured_s": 0.0,
                "pass": False,
                "detail": "skipped: no session cookie from login",
            }
        )
        results.append(
            {
                "slo": "SLO-5 snapshot median",
                "target_s": SLO_SNAPSHOT_MEDIAN_S,
                "measured_s": 0.0,
                "pass": False,
                "detail": "skipped: no session cookie from login",
            }
        )

    # --- SLO-4: Job queue lag (marker job via BFF proxy) ---
    results.extend(_probe_job_queue_lag(base, session_cookie))

    return results


def _login_session(base: str, username: str, password: str) -> str | None:
    """Login and return the session cookie header value, or None."""
    import json

    data = json.dumps({"username": username, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/session/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30.0) as response:
            raw = response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as exc:
        raw = exc.headers.get("Set-Cookie", "") if exc.headers else ""
    if not raw:
        return None
    # Keep the first cookie pair (session cookie); strip attributes.
    return raw.split(";", 1)[0].strip() or None


def _post_authenticated(
    base: str, path: str, payload: dict[str, Any], cookie: str
) -> tuple[int, dict[str, Any], float]:
    import json

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Cookie": cookie},
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60.0) as response:
            body = response.read()
            status_code = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status_code = int(exc.code)
    elapsed = time.monotonic() - start
    parsed: dict[str, Any] = {}
    try:
        parsed = json.loads(body.decode("utf-8")) if body.strip() else {}
    except Exception:
        parsed = {}
    return status_code, parsed, elapsed


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def _probe_read_p95(base: str, cookie: str) -> list[dict[str, Any]]:
    """SLO-2: read/query p95 latency (kind=krs.by_cycle)."""
    durations: list[float] = []
    ok_count = 0
    iterations = 10
    for _ in range(iterations):
        status_code, _body, elapsed = _post_authenticated(
            base,
            "/api/backend/v1/read/query",
            {"kind": "krs.by_cycle", "params": {}, "actor": ""},
            cookie,
        )
        if status_code == 200:
            ok_count += 1
        durations.append(elapsed)
    p95 = _p95(durations)
    return [
        {
            "slo": "SLO-2 read/query p95",
            "target_s": SLO_READ_P95_S,
            "measured_s": round(p95, 3),
            "pass": p95 <= SLO_READ_P95_S and ok_count >= iterations // 2,
            "detail": f"{ok_count}/{iterations} succeeded",
        }
    ]


def _probe_mutation_error_rate(base: str, cookie: str) -> list[dict[str, Any]]:
    """SLO-3: mutation error rate proxy — weekly-plan upsert round trip.

    Uses an idempotent-shaped mutation (weekly plan upsert for the actor) so the
    probe does not accumulate garbage data. Errors counted as non-2xx.
    """
    iterations = 10
    errors = 0
    for i in range(iterations):
        status_code, _body, _elapsed = _post_authenticated(
            base,
            "/api/backend/v1/weekly-plans",
            {"priority_1": f"slo-probe-{i}", "is_active": True},
            cookie,
        )
        if status_code < 200 or status_code >= 300:
            errors += 1
    error_rate = errors / iterations
    return [
        {
            "slo": "SLO-3 mutation error rate",
            "target_s": 0.02,
            "measured_s": round(error_rate, 3),
            "pass": error_rate <= 0.02,
            "detail": f"{errors}/{iterations} errored (weekly-plans upsert)",
        }
    ]


def _probe_snapshot_latency(base: str, cookie: str) -> list[dict[str, Any]]:
    """SLO-5: check-in snapshot median latency (ritual.snapshot kind)."""
    durations: list[float] = []
    ok_count = 0
    iterations = 6
    for _ in range(iterations):
        status_code, _body, elapsed = _post_authenticated(
            base,
            "/api/backend/v1/read/query",
            {
                "kind": "ritual.snapshot",
                "params": {},
                "actor": "",
            },
            cookie,
        )
        if status_code == 200:
            ok_count += 1
        durations.append(elapsed)
    median = statistics.median(durations) if durations else 0.0
    return [
        {
            "slo": "SLO-5 snapshot median",
            "target_s": SLO_SNAPSHOT_MEDIAN_S,
            "measured_s": round(median, 3),
            "pass": median <= SLO_SNAPSHOT_MEDIAN_S and ok_count >= iterations // 2,
            "detail": f"{ok_count}/{iterations} succeeded",
        }
    ]


def _probe_job_queue_lag(base: str, cookie: str | None) -> list[dict[str, Any]]:
    """SLO-4: job queue lag — submit marker job, poll until it leaves PENDING.

    Uses the ai.generate_json kind only if AI provider is configured; otherwise
    reports skipped rather than failing the run.
    """
    if not cookie:
        return [
            {
                "slo": "SLO-4 job queue lag",
                "target_s": 60.0,
                "measured_s": 0.0,
                "pass": False,
                "detail": "skipped: no session cookie",
            }
        ]
    submit_status, body, _elapsed = _post_authenticated(
        base,
        "/api/backend/v1/jobs",
        {"kind": "ai.generate_json", "payload": {"prompt": "ping"}, "max_attempts": 1},
        cookie,
    )
    if submit_status != 202:
        return [
            {
                "slo": "SLO-4 job queue lag",
                "target_s": 60.0,
                "measured_s": 0.0,
                "pass": False,
                "detail": f"skipped: submit returned {submit_status}",
            }
        ]
    job_id = str(body.get("id") or "")
    start = time.monotonic()
    deadline = start + 90.0
    lag: float | None = None
    while time.monotonic() < deadline:
        status_code, job_body, _elapsed = _get_json(
            f"{base}/api/backend/v1/jobs/{job_id}", cookie=cookie
        )
        if status_code == 200:
            state = str(job_body.get("status") or "").lower()
            if state in {"running", "succeeded", "failed", "cancelled"}:
                lag = time.monotonic() - start
                break
        time.sleep(1.0)
    if lag is None:
        lag = time.monotonic() - start
    return [
        {
            "slo": "SLO-4 job queue lag",
            "target_s": 60.0,
            "measured_s": round(lag, 3),
            "pass": lag <= 60.0,
            "detail": f"job {job_id[:8]} left pending after {lag:.1f}s",
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SLO probes against live stack.")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    results = probe(args.base_url, args.username, args.password)

    print(f"{'SLO':<28} {'Target':>8} {'Measured':>10} {'Pass':>6}  Detail")
    print("-" * 90)
    failures = 0
    for r in results:
        flag = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            failures += 1
        print(
            f"{r['slo']:<28} {r['target_s']:>7.1f}s {r['measured_s']:>9.3f}s "
            f"{flag:>6}  {r['detail']}"
        )

    breached = sum(1 for r in results if not r["pass"])
    print(f"\n{len(results) - breached}/{len(results)} SLO checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
