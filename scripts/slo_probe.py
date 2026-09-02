# ruff: noqa: E402
"""SLO probe: measure live SLO targets defined in docs/OBSERVABILITY_AND_RUNBOOKS.md.

Runs against a live stack (BFF + backend). Produces per-SLO pass/fail against
targets and exits non-zero on any breach.

Usage:
    python scripts/slo_probe.py --base-url http://localhost:3000 \
        --username admin --password <pw>

Requires a reachable stack. The authenticated mutation checks use one weekly
upsert window and one stable job idempotency key, so repeated runs do not
accumulate probe data or queued jobs.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import urllib.error
import urllib.request

# SLO targets from docs/OBSERVABILITY_AND_RUNBOOKS.md
SLO_LOGIN_P95_S = 3.0
SLO_READ_P95_S = 1.5
SLO_SNAPSHOT_MEDIAN_S = 1.0
PROBE_ITERATIONS = 10
_SERVER_TIMING_PART = re.compile(
    r"(?:^|,)\s*(?P<name>[a-z][a-z0-9_-]*)\s*;dur=(?P<duration>[0-9]+(?:\.[0-9]+)?)\s*(?=,|$)",
    re.IGNORECASE,
)


def _parse_server_timing(value: str | None) -> dict[str, float]:
    """Parse only safe Server-Timing metric durations for probe attribution."""
    timings: dict[str, float] = {}
    for match in _SERVER_TIMING_PART.finditer(str(value or "")):
        name = match.group("name").lower()
        if len(name) > 32:
            continue
        timings[name] = max(0.0, float(match.group("duration")))
    return timings


def _timing_summary(samples: list[dict[str, float]]) -> str:
    """Return stable, non-sensitive p50 timing attribution for human evidence."""
    if not samples:
        return ""
    names = sorted({name for sample in samples for name in sample})
    if not names:
        return ""
    values = []
    for name in names:
        durations = [sample[name] for sample in samples if name in sample]
        values.append(f"{name}_p50_ms={statistics.median(durations):.1f}")
    return "timing=" + ",".join(values)


def _timing_medians(samples: list[dict[str, float]]) -> dict[str, float]:
    """Return machine-readable p50 attribution without request metadata."""
    names = sorted({name for sample in samples for name in sample})
    return {
        name: round(statistics.median([sample[name] for sample in samples if name in sample]), 3)
        for name in names
    }


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


def probe(
    base_url: str,
    username: str,
    password: str,
    *,
    prepare_snapshot_fixture: bool = False,
) -> list[dict[str, Any]]:
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
    status_code, body, elapsed = _get_json(f"{base}/api/healthz")
    dead_jobs = body.get("dead_jobs") if isinstance(body, dict) else None
    data_access_mode = (
        str(body.get("data_access_mode") or "").strip().lower()
        if isinstance(body, dict)
        else ""
    )
    results.append(
        {
            "slo": "healthz reachable",
            "target_s": 2.0,
            "measured_s": round(elapsed, 3),
            "pass": status_code == 200 and elapsed <= 2.0,
            "detail": f"status={status_code} dead_jobs={dead_jobs} "
            f"mode={data_access_mode or '?'}",
        }
    )

    # --- Authenticated probes (SLO-2..5) require a session cookie. ---
    session = _login_session(base, username, password)
    cleanup_cycle_id: int | None = None
    if session:
        session_cookie, csrf_token = session
        probe_context = _probe_actor_context(
            base, session_cookie, username, csrf_token
        )
        snapshot_context, cleanup_cycle_id = _snapshot_context(
            base,
            session_cookie,
            username,
            csrf_token,
            allow_create=prepare_snapshot_fixture,
        )
        effective_context = snapshot_context or probe_context
        try:
            results.extend(
                _probe_read_p95(base, session_cookie, effective_context, csrf_token)
            )
            results.extend(
                _probe_mutation_error_rate(
                    base, session_cookie, effective_context, csrf_token
                )
            )
            results.extend(
                _probe_snapshot_latency(
                    base, session_cookie, snapshot_context, csrf_token
                )
            )
        finally:
            if cleanup_cycle_id is not None:
                _cleanup_snapshot_cycle(
                    base, session_cookie, cleanup_cycle_id, csrf_token
                )
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
    results.extend(
        _probe_job_queue_lag(
            base,
            session[0] if session else None,
            session[1] if session else None,
            data_access_mode=data_access_mode,
        )
    )

    return results


def _login_session(
    base: str, username: str, password: str
) -> tuple[str, str] | None:
    """Login and return session and CSRF cookie values, or None."""
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
            raw_headers = response.headers
    except urllib.error.HTTPError as exc:
        raw_headers = exc.headers
    if not raw_headers:
        return None
    cookie_headers = []
    get_all = getattr(raw_headers, "get_all", None)
    if callable(get_all):
        cookie_headers = list(get_all("Set-Cookie") or [])
    if not cookie_headers:
        raw = raw_headers.get("Set-Cookie", "")
        cookie_headers = [raw] if raw else []

    cookies: dict[str, str] = {}
    for header in cookie_headers:
        for part in str(header).split(","):
            cookie_pair = part.split(";", 1)[0].strip()
            if "=" not in cookie_pair:
                continue
            name, value = cookie_pair.split("=", 1)
            cookies[name.strip()] = value.strip()
    session_cookie = cookies.get("okr_spa_session")
    csrf_token = cookies.get("okr_csrf_token")
    if not session_cookie or not csrf_token:
        return None
    # The BFF validates the header against the CSRF cookie as well as the
    # session cookie. Sending only the session cookie makes every state change
    # fail with INVALID_CSRF_TOKEN even when the header is correct.
    return (
        f"okr_spa_session={session_cookie}; okr_csrf_token={csrf_token}",
        csrf_token,
    )


def _post_authenticated(
    base: str,
    path: str,
    payload: dict[str, Any],
    cookie: str,
    *,
    idempotency_key: str | None = None,
    csrf_token: str | None = None,
    timing_sink: list[dict[str, float]] | None = None,
) -> tuple[int, dict[str, Any], float]:
    import json

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Cookie": cookie}
    if csrf_token:
        headers["X-XSRF-TOKEN"] = csrf_token
    if idempotency_key:
        headers["X-OKR-Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60.0) as response:
            body = response.read()
            status_code = int(response.status)
            timing_header = response.headers.get("Server-Timing")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status_code = int(exc.code)
        timing_header = exc.headers.get("Server-Timing") if exc.headers else None
    elapsed = time.monotonic() - start
    if timing_sink is not None:
        timing_sink.append(_parse_server_timing(timing_header))
    parsed: dict[str, Any] = {}
    try:
        parsed = json.loads(body.decode("utf-8")) if body.strip() else {}
    except Exception:
        parsed = {}
    return status_code, parsed, elapsed


def _delete_authenticated(
    base: str,
    path: str,
    cookie: str,
    *,
    csrf_token: str | None = None,
    timeout: float = 60.0,
) -> tuple[int, dict[str, Any], float]:
    """DELETE an authenticated disposable resource and return its response."""
    import json

    headers = {"Cookie": cookie}
    if csrf_token:
        headers["X-XSRF-TOKEN"] = csrf_token
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}", headers=headers, method="DELETE"
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
    try:
        parsed = json.loads(body.decode("utf-8")) if body.strip() else {}
    except Exception:
        parsed = {}
    return status_code, parsed if isinstance(parsed, dict) else {}, elapsed


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def _probe_read_p95(
    base: str,
    cookie: str,
    context: dict[str, int] | None,
    csrf_token: str | None = None,
) -> list[dict[str, Any]]:
    """SLO-2: read/query p95 latency (kind=krs.by_cycle)."""
    durations: list[float] = []
    timing_samples: list[dict[str, float]] = []
    ok_count = 0
    iterations = 10
    for _ in range(iterations):
        status_code, _body, elapsed = _post_authenticated(
            base,
            "/api/backend/v1/read/query",
            {
                "kind": "krs.by_cycle",
                "params": {"cycle_id": context["cycle_id"] if context else 0},
                "actor_username": "",
            },
            cookie,
            csrf_token=csrf_token,
            timing_sink=timing_samples,
        )
        if status_code == 200:
            ok_count += 1
        durations.append(elapsed)
    p95 = _p95(durations)
    timing_detail = _timing_summary(timing_samples)
    attribution = _timing_medians(timing_samples)
    detail = f"{ok_count}/{iterations} succeeded"
    if timing_detail:
        detail = f"{detail}; {timing_detail}"
    return [
        {
            "slo": "SLO-2 read/query p95",
            "target_s": SLO_READ_P95_S,
            "measured_s": round(p95, 3),
            "pass": p95 <= SLO_READ_P95_S and ok_count >= iterations // 2,
            "detail": detail,
            "attribution_ms": attribution,
        }
    ]


def _probe_actor_context(
    base: str, cookie: str, username: str, csrf_token: str | None = None
) -> dict[str, int] | None:
    """Resolve the authenticated user and active cycle for contract probes."""
    user_status, user_body, _ = _post_authenticated(
        base,
        "/api/backend/v1/read/query",
        {
            "kind": "users.by_username",
            "params": {"username": username},
            "actor_username": username,
        },
        cookie,
        csrf_token=csrf_token,
    )
    cycles_status, cycles_body, _ = _post_authenticated(
        base,
        "/api/backend/v1/read/query",
        {
            "kind": "cycles.active",
            "params": {},
            "actor_username": username,
        },
        cookie,
        csrf_token=csrf_token,
    )
    user = user_body.get("user") if isinstance(user_body, dict) else None
    cycles = cycles_body.get("cycles") if isinstance(cycles_body, dict) else None
    if user_status != 200 or not isinstance(user, dict) or not user.get("id"):
        return None
    if user_status != 200 or not isinstance(user, dict) or not user.get("id"):
        return None
    if cycles_status != 200 or not isinstance(cycles, list) or not cycles:
        # Weekly-plan writes are scoped to the authenticated user and do not
        # require a cycle. Keep that valid user context so a missing cycle does
        # not turn the mutation fixture into the invalid user_id=0 payload.
        return {"user_id": int(user["id"]), "cycle_id": 0}
    cycle = cycles[0]
    if not isinstance(cycle, dict) or not cycle.get("id"):
        return {"user_id": int(user["id"]), "cycle_id": 0}
    return {"user_id": int(user["id"]), "cycle_id": int(cycle["id"])}


def _snapshot_context(
    base: str,
    cookie: str,
    username: str,
    csrf_token: str | None = None,
    *,
    allow_create: bool = False,
) -> tuple[dict[str, int] | None, int | None]:
    """Return a valid snapshot context and the ID of any disposable cycle created."""
    context = _probe_actor_context(base, cookie, username, csrf_token)
    if context and context.get("cycle_id", 0) > 0:
        return context, None
    if not allow_create or not context or context.get("user_id", 0) <= 0:
        return None, None

    status, body, _elapsed = _post_authenticated(
        base,
        "/api/backend/v1/read/query",
        {
            "kind": "users.by_username",
            "params": {"username": username},
            "actor_username": username,
        },
        cookie,
        csrf_token=csrf_token,
    )
    user = body.get("user") if isinstance(body, dict) else None
    role = str(user.get("role") or "").strip().lower() if isinstance(user, dict) else ""
    if status != 200 or role != "admin":
        return None, None

    # Cycle creation in the application preserves the active-cycle invariant
    # by deactivating existing active cycles. Refuse the disposable setup unless
    # the authenticated probe can confirm that none exist anywhere in scope.
    status, body, _elapsed = _post_authenticated(
        base,
        "/api/backend/v1/read/query",
        {
            "kind": "cycles.all",
            "params": {},
            "actor_username": username,
        },
        cookie,
        csrf_token=csrf_token,
    )
    cycles = body.get("cycles") if isinstance(body, dict) else None
    if status != 200 or not isinstance(cycles, list):
        return None, None
    if any(isinstance(cycle, dict) and cycle.get("is_active") is True for cycle in cycles):
        return None, None

    start_date, end_date = _current_probe_week()
    title = f"[SLO PROBE] disposable snapshot cycle {context['user_id']}"
    status, body, _elapsed = _post_authenticated(
        base,
        "/api/backend/v1/cycles",
        {
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "is_active": True,
            "owner_manager_id": context["user_id"],
            "actor_username": username,
        },
        cookie,
        csrf_token=csrf_token,
    )
    cycle_id = body.get("id") if isinstance(body, dict) else None
    if (
        status < 200
        or status >= 300
        or not isinstance(cycle_id, int)
        or cycle_id <= 0
        or body.get("title") != title
        or body.get("is_active") is not True
        or int(body.get("owner_manager_id") or 0) != context["user_id"]
    ):
        return None, None
    return {"user_id": context["user_id"], "cycle_id": cycle_id}, cycle_id


def _cleanup_snapshot_cycle(
    base: str, cookie: str, cycle_id: int, csrf_token: str | None = None
) -> bool:
    """Delete only the cycle created by this probe invocation."""
    status, body, _elapsed = _delete_authenticated(
        base,
        f"/api/backend/v1/cycles/{int(cycle_id)}",
        cookie,
        csrf_token=csrf_token,
    )
    return 200 <= status < 300 and body.get("deleted") is True


def _current_probe_week() -> tuple[str, str]:
    """Return a stable UTC week window for the idempotent weekly-plan upsert."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start.isoformat(), end.isoformat()


def _probe_mutation_error_rate(
    base: str,
    cookie: str,
    context: dict[str, int] | None,
    csrf_token: str | None = None,
) -> list[dict[str, Any]]:
    """SLO-3: mutation error rate proxy — weekly-plan upsert round trip.

    Uses an idempotent-shaped mutation (weekly plan upsert for the actor) so the
    probe does not accumulate garbage data. Errors counted as non-2xx.
    """
    iterations = 10
    errors = 0
    start_date, end_date = _current_probe_week()
    for _ in range(iterations):
        payload = {
            "user_id": context["user_id"] if context else 0,
            "start_date": start_date,
            "end_date": end_date,
            "p1": "SLO probe no-op",
            "p2": None,
            "p3": None,
            "actor_username": "",
        }
        status_code, _body, _elapsed = _post_authenticated(
            base,
            "/api/backend/v1/weekly-plans",
            payload,
            cookie,
            csrf_token=csrf_token,
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


def _probe_snapshot_latency(
    base: str,
    cookie: str,
    context: dict[str, int] | None,
    csrf_token: str | None = None,
) -> list[dict[str, Any]]:
    """SLO-5: check-in snapshot median latency (ritual.snapshot kind)."""
    if not context or context.get("user_id", 0) <= 0 or context.get("cycle_id", 0) <= 0:
        return [
            {
                "slo": "SLO-5 snapshot median",
                "target_s": SLO_SNAPSHOT_MEDIAN_S,
                "measured_s": 0.0,
                "pass": False,
                "detail": "unavailable: active cycle prerequisite not met",
            }
        ]
    durations: list[float] = []
    ok_count = 0
    iterations = 6
    window_start, window_end = _current_probe_week()
    for _ in range(iterations):
        status_code, _body, elapsed = _post_authenticated(
            base,
            "/api/backend/v1/read/query",
            {
                "kind": "ritual.snapshot",
                "params": {
                    "user_id": context["user_id"] if context else 0,
                    "cycle_id": context["cycle_id"] if context else 0,
                    "actor_username": "",
                    "window_start": window_start,
                    "window_end": window_end,
                    "days_threshold": 7,
                },
                "actor_username": "",
            },
            cookie,
            csrf_token=csrf_token,
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


def _probe_job_queue_lag(
    base: str,
    cookie: str | None,
    csrf_token: str | None = None,
    *,
    data_access_mode: str = "",
) -> list[dict[str, Any]]:
    """SLO-4: job queue lag — submit marker job, poll until it leaves PENDING.

    Uses a deterministic, empty PDF report and idempotency key so the check does
    not require an AI provider or accumulate jobs across probe runs.
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
        {
            "kind": "pdf.weekly",
            "payload": {
                "report_items": [],
                "objective_stats": {},
                "key_results": [],
                "total_time_str": "00:00",
                "title": "SLO probe",
                "time_label": "Probe",
                "filename": "slo-probe.pdf",
            },
            "max_attempts": 1,
        },
        cookie,
        idempotency_key="slo-probe-weekly-pdf",
        csrf_token=csrf_token,
    )
    if submit_status != 202:
        if submit_status == 503 and data_access_mode == "supabase_api":
            return [
                {
                    "slo": "SLO-4 job queue lag",
                    "target_s": 60.0,
                    "measured_s": 0.0,
                    "pass": True,
                    "detail": (
                        "skipped: async job store is intentionally unavailable "
                        "in supabase_api mode"
                    ),
                }
            ]
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
    parser.add_argument(
        "--prepare-snapshot-fixture",
        action="store_true",
        help="Create and delete a probe-owned active cycle when none is accessible.",
    )
    parser.add_argument(
        "--confirm-disposable",
        action="store_true",
        help="Required with --prepare-snapshot-fixture for explicit disposable opt-in.",
    )
    args = parser.parse_args()

    if args.prepare_snapshot_fixture and not args.confirm_disposable:
        parser.error("--prepare-snapshot-fixture requires --confirm-disposable")

    results = probe(
        args.base_url,
        args.username,
        args.password,
        prepare_snapshot_fixture=args.prepare_snapshot_fixture,
    )

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
