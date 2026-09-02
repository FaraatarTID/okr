"""In-memory observability metrics for runtime services.

This module intentionally stores counters and latency samples only in memory.
It is used by API, worker, and provider paths to provide quick dashboard-ready
signals without introducing a heavy telemetry dependency.
"""

from __future__ import annotations

import json
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.observability_redaction import redact_observability


_SAMPLE_LIMIT = 240
_STARTED_AT = time.time()
_LOCK = threading.Lock()


def _safe_text(value: object, *, max_length: int = 128) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_length]


def _route_key(method: object, path: object) -> str:
    verb = str(method or "").strip().upper()[:16]
    route = str(path or "").strip() or "/"
    if not route.startswith("/"):
        route = f"/{route}"
    return f"{verb} {route}"


def _status_group(status_code: int | float | str | None) -> str:
    try:
        if status_code is None:
            return "unknown"
        value = int(status_code)
    except (TypeError, ValueError):
        return "unknown"
    return f"{(value // 100) * 100}"


def _percentile(samples: list[float], percentage: int) -> Optional[float]:
    if not samples:
        return None
    if percentage <= 0:
        return samples[0]
    if percentage >= 100:
        return samples[-1]
    index = int((len(samples) - 1) * (percentage / 100))
    return samples[index]


@dataclass
class _LatencyTracker:
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=_SAMPLE_LIMIT))

    def observe(self, value_ms: float) -> None:
        measured = max(0.0, float(value_ms))
        self.count += 1
        self.total_ms += measured
        if measured > self.max_ms:
            self.max_ms = measured
        self.samples.append(measured)

    def snapshot(self) -> dict[str, Any]:
        if self.count <= 0:
            return {
                "count": 0,
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
            }

        sorted_samples = sorted(self.samples)
        return {
            "count": int(self.count),
            "avg_ms": round(self.total_ms / max(1, self.count), 3),
            "max_ms": round(self.max_ms, 3),
            "p50_ms": round(_percentile(sorted_samples, 50) or 0.0, 3),
            "p95_ms": round(_percentile(sorted_samples, 95) or 0.0, 3),
            "p99_ms": round(_percentile(sorted_samples, 99) or 0.0, 3),
        }


@dataclass
class _RouteMetrics:
    requests: int = 0
    errors: int = 0
    latencies: _LatencyTracker = field(default_factory=_LatencyTracker)
    status: Counter[str] = field(default_factory=lambda: Counter())
    strategies: Counter[str] = field(default_factory=lambda: Counter())
    fallback_reasons: Counter[str] = field(default_factory=lambda: Counter())
    resolver_states: Counter[str] = field(default_factory=lambda: Counter())
    last_seen_unix_ts: float = 0.0


@dataclass
class _ProviderMetrics:
    calls: int = 0
    errors: int = 0
    latencies: _LatencyTracker = field(default_factory=_LatencyTracker)
    error_breakdown: Counter[str] = field(default_factory=lambda: Counter())


@dataclass
class _WorkerMetrics:
    iterations: int = 0
    jobs_submitted: int = 0
    jobs_started: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    jobs_rejected: int = 0
    last_heartbeat_unix_ts: float = 0.0
    queue_depth_history: deque[float] = field(
        default_factory=lambda: deque(maxlen=_SAMPLE_LIMIT)
    )
    latencies: dict[str, _LatencyTracker] = field(
        default_factory=lambda: defaultdict(_LatencyTracker)
    )


_ROUTE_METRICS: Dict[str, _RouteMetrics] = defaultdict(_RouteMetrics)
_PROVIDER_METRICS: Dict[str, _ProviderMetrics] = defaultdict(_ProviderMetrics)
_WORKER_METRICS = _WorkerMetrics()
_ACTIVE_WORKERS: set[str] = set()


def record_api_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
    actor: str | None = None,
    strategy: str | None = None,
    fallback_reason: str | None = None,
    resolver_state: str | None = None,
) -> None:
    metric_key = _route_key(method, route)
    status_key = _status_group(status_code)
    with _LOCK:
        bucket = _ROUTE_METRICS[metric_key]
        bucket.requests += 1
        bucket.last_seen_unix_ts = time.time()
        bucket.latencies.observe(duration_ms)
        bucket.status[str(status_key)] += 1
        if actor:
            bucket.status[f"actor:{_safe_text(actor, max_length=24)}"] += 1
        if strategy:
            bucket.strategies[_safe_text(strategy, max_length=32)] += 1
        if fallback_reason:
            bucket.fallback_reasons[_safe_text(fallback_reason, max_length=64)] += 1
        if resolver_state:
            bucket.resolver_states[_safe_text(resolver_state, max_length=64)] += 1
        if int(status_code) >= 400:
            bucket.errors += 1


def record_provider_call(
    *,
    provider: str,
    success: bool,
    latency_ms: float,
    error_code: str | None = None,
) -> None:
    key = _safe_text(provider, max_length=96)
    with _LOCK:
        bucket = _PROVIDER_METRICS[key]
        bucket.calls += 1
        bucket.latencies.observe(latency_ms)
        if not success:
            bucket.errors += 1
            if error_code:
                bucket_key = f"error:{_safe_text(error_code, max_length=96)}"
                bucket.error_breakdown[bucket_key] += 1


def record_worker_heartbeat(*, worker_id: str) -> None:
    with _LOCK:
        _WORKER_METRICS.iterations += 1
        _WORKER_METRICS.last_heartbeat_unix_ts = time.time()
        _ACTIVE_WORKERS.add(_safe_text(worker_id, max_length=64))


def record_worker_job_started(*, worker_id: str, kind: str) -> None:
    with _LOCK:
        _WORKER_METRICS.jobs_started += 1
        _ACTIVE_WORKERS.add(_safe_text(worker_id, max_length=64))


def record_worker_job_result(
    *,
    worker_id: str,
    kind: str,
    success: bool,
    duration_ms: float,
    outcome: str | None = None,
) -> None:
    normalized_kind = _safe_text(kind, max_length=96).lower() or "unknown"
    outcome_key = _safe_text(outcome or "failure" if not success else "success")
    with _LOCK:
        if success:
            _WORKER_METRICS.jobs_succeeded += 1
        else:
            _WORKER_METRICS.jobs_failed += 1
        if outcome_key == "rejected":
            _WORKER_METRICS.jobs_rejected += 1
        _WORKER_METRICS.latencies[normalized_kind].observe(duration_ms)
        _ACTIVE_WORKERS.add(_safe_text(worker_id, max_length=64))


def record_worker_queue_depth(pending: int, running: int) -> None:
    queue_depth = max(0.0, float(pending) + float(running))
    with _LOCK:
        _WORKER_METRICS.queue_depth_history.append(queue_depth)


def record_job_submission(*, kind: str) -> None:
    with _LOCK:
        # Jobs are recorded as submitted so dashboards can see enqueue pressure.
        _WORKER_METRICS.jobs_submitted += 1


def snapshot() -> dict[str, Any]:
    with _LOCK:
        now = time.time()
        route_metrics = []
        for route, route_bucket in sorted(_ROUTE_METRICS.items()):
            value_snapshot = route_bucket.latencies.snapshot()
            route_metrics.append(
                {
                    "route": route,
                    "requests": int(route_bucket.requests),
                    "errors": int(route_bucket.errors),
                    "last_seen_at": datetime.fromtimestamp(
                        route_bucket.last_seen_unix_ts, tz=timezone.utc
                    ).isoformat(),
                    "status_counts": dict(route_bucket.status),
                    "strategy_counts": dict(route_bucket.strategies),
                    "fallback_reason_counts": dict(route_bucket.fallback_reasons),
                    "resolver_state_counts": dict(route_bucket.resolver_states),
                    **value_snapshot,
                }
            )

        provider_metrics = []
        for provider_name, provider_bucket in sorted(_PROVIDER_METRICS.items()):
            provider_snapshot = provider_bucket.latencies.snapshot()
            provider_metrics.append(
                {
                    "provider": provider_name,
                    "calls": int(provider_bucket.calls),
                    "errors": int(provider_bucket.errors),
                    **provider_snapshot,
                }
            )

        worker_kind_latencies = {}
        for kind, value in sorted(_WORKER_METRICS.latencies.items()):
            worker_kind_latencies[kind] = value.snapshot()

        queue_depth_samples = list(_WORKER_METRICS.queue_depth_history)
        queue_depth_avg = (
            round(sum(queue_depth_samples) / len(queue_depth_samples), 3)
            if queue_depth_samples
            else 0.0
        )

        return {
            "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "window_seconds": round(now - _STARTED_AT, 3),
            "requests": {
                "by_route": route_metrics,
                "active_routes": len(route_metrics),
                "total_routes": len(route_metrics),
                "total_requests": sum(item["requests"] for item in route_metrics),
            },
            "providers": {
                "by_provider": provider_metrics,
            },
            "worker": {
                "iterations": int(_WORKER_METRICS.iterations),
                "jobs_submitted": int(_WORKER_METRICS.jobs_submitted),
                "jobs_started": int(_WORKER_METRICS.jobs_started),
                "jobs_succeeded": int(_WORKER_METRICS.jobs_succeeded),
                "jobs_failed": int(_WORKER_METRICS.jobs_failed),
                "jobs_rejected": int(_WORKER_METRICS.jobs_rejected),
                "active_workers": sorted(_ACTIVE_WORKERS),
                "active_worker_count": len(_ACTIVE_WORKERS),
                "queue_depth_avg": queue_depth_avg,
                "last_heartbeat_at": (
                    datetime.fromtimestamp(
                        _WORKER_METRICS.last_heartbeat_unix_ts, tz=timezone.utc
                    ).isoformat()
                    if _WORKER_METRICS.last_heartbeat_unix_ts
                    else None
                ),
                "job_duration_by_kind_ms": worker_kind_latencies,
            },
        }


def log_payload(*, event: str, **fields: Any) -> str:
    payload = {
        "event": _safe_text(event, max_length=64),
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    return json.dumps(redact_observability(payload), ensure_ascii=False, default=str)
