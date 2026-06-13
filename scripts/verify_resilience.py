#!/usr/bin/env python3
"""Run resilience verification checks for distributed cache and URL state recovery."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/test_distributed_state_service.py",
    "tests/test_cache_utils.py",
    "tests/test_hot_reload_cache_invalidation.py",
    "tests/test_crud_backend_mutation_proxy.py",
    "tests/test_app_query_helpers.py",
    "tests/test_app_auth_helpers.py",
    "tests/test_atlas_workspace_scope_helpers.py",
    "tests/test_atlas_navigation_helpers.py",
    "tests/test_atlas_focus_selection_helpers.py",
    "tests/test_atlas_map_sidebar_helpers.py",
    "tests/test_atlas_map_chart_helpers.py",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def _run_command(argv: list[str], *, cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(
        [chunk for chunk in [completed.stdout, completed.stderr] if chunk]
    ).strip()
    return int(completed.returncode), output


def _run_pytest(*, targets: Iterable[str], extra_args: Iterable[str]) -> CheckResult:
    test_targets = [str(target).strip() for target in targets if str(target).strip()]
    if not test_targets:
        return CheckResult(
            name="pytest_resilience_suite",
            status="skip",
            detail="No pytest targets specified.",
        )

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *test_targets,
        *[str(arg) for arg in extra_args if str(arg).strip()],
    ]
    print(f"Running: {' '.join(cmd)}")
    return_code, output = _run_command(cmd, cwd=ROOT)
    if return_code != 0:
        detail = (
            output or "Pytest exited with a non-zero status and no output was captured."
        )
        return CheckResult(
            name="pytest_resilience_suite",
            status="fail",
            detail=detail,
        )

    return CheckResult(
        name="pytest_resilience_suite",
        status="pass",
        detail=output or "Pytest suite passed.",
    )


def _bootstrap_import_path() -> None:
    root_src = str(ROOT.resolve())
    if root_src not in sys.path:
        sys.path.insert(0, root_src)


def _run_live_backend_checks(
    *,
    actor_username: str,
    probe_key_prefix: str,
    require_live_backend: bool,
) -> list[CheckResult]:
    _bootstrap_import_path()
    from src.config_runtime import get_config_value
    from src.services import distributed_state_service

    backend_url = str(get_config_value("OKR_BACKEND_API_URL", "")).strip()
    if not backend_url:
        status = "fail" if require_live_backend else "skip"
        return [
            CheckResult(
                name="live_distributed_state_roundtrip",
                status=status,
                detail=(
                    "OKR_BACKEND_API_URL is empty. "
                    "Set backend URL and service credentials to run live checks."
                ),
            )
        ]

    now_ns = int(time.time_ns())
    probe_key = f"{str(probe_key_prefix).strip()}:{now_ns}:roundtrip"
    probe_value = str(now_ns)

    results: list[CheckResult] = []

    set_ok = distributed_state_service.set_distributed_state(
        probe_key,
        probe_value,
        actor_username=actor_username,
    )
    if not set_ok:
        results.append(
            CheckResult(
                name="live_distributed_state_roundtrip",
                status="fail",
                detail=(
                    "Failed to set distributed state probe key. "
                    "Check backend URL/token/signing config and backend health."
                ),
            )
        )
        return results

    roundtrip_value = distributed_state_service.get_distributed_state(
        probe_key,
        actor_username=actor_username,
    )
    if roundtrip_value != probe_value:
        results.append(
            CheckResult(
                name="live_distributed_state_roundtrip",
                status="fail",
                detail=(
                    f"Roundtrip mismatch for '{probe_key}': "
                    f"expected '{probe_value}', got '{roundtrip_value}'."
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="live_distributed_state_roundtrip",
                status="pass",
                detail=f"Probe key '{probe_key}' set/read roundtrip succeeded.",
            )
        )

    before_ts = distributed_state_service.get_last_invalidation_timestamp()
    broadcast_ok = distributed_state_service.broadcast_cache_invalidation(
        actor_username=actor_username
    )
    after_ts = distributed_state_service.get_last_invalidation_timestamp()

    if not broadcast_ok:
        results.append(
            CheckResult(
                name="live_cache_invalidation_signal",
                status="fail",
                detail="Failed to broadcast cache invalidation signal.",
            )
        )
    elif int(after_ts) <= int(before_ts):
        results.append(
            CheckResult(
                name="live_cache_invalidation_signal",
                status="fail",
                detail=(
                    "Invalidation timestamp did not advance. "
                    f"before={before_ts}, after={after_ts}."
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="live_cache_invalidation_signal",
                status="pass",
                detail=f"Invalidation timestamp advanced: {before_ts} -> {after_ts}.",
            )
        )

    return results


def _print_results(results: list[CheckResult]) -> None:
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.detail}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run resilience verification checks for distributed cache invalidation "
            "and URL-state failover support."
        )
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip the default resilience pytest subset.",
    )
    parser.add_argument(
        "--pytest-target",
        action="append",
        default=[],
        help=(
            "Additional pytest target to include. "
            "If any are provided, they are appended to the default subset."
        ),
    )
    parser.add_argument(
        "--extra-pytest-arg",
        action="append",
        default=[],
        help="Extra argument forwarded to pytest (can be specified multiple times).",
    )
    parser.add_argument(
        "--live-backend-check",
        action="store_true",
        help="Run live backend distributed-state checks through backend API endpoints.",
    )
    parser.add_argument(
        "--require-live-backend",
        action="store_true",
        help="Fail if live backend checks cannot run or do not pass.",
    )
    parser.add_argument(
        "--actor",
        default="system",
        help="Actor username used for live backend checks (default: system).",
    )
    parser.add_argument(
        "--probe-key-prefix",
        default="okr:resilience:probe",
        help="Distributed-state probe key prefix for live checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    run_live = bool(args.live_backend_check or args.require_live_backend)

    results: list[CheckResult] = []

    if not args.skip_pytest:
        combined_targets = list(DEFAULT_PYTEST_TARGETS)
        combined_targets.extend(args.pytest_target)
        results.append(
            _run_pytest(
                targets=combined_targets,
                extra_args=args.extra_pytest_arg,
            )
        )

    if run_live:
        results.extend(
            _run_live_backend_checks(
                actor_username=str(args.actor).strip() or "system",
                probe_key_prefix=str(args.probe_key_prefix).strip()
                or "okr:resilience:probe",
                require_live_backend=bool(args.require_live_backend),
            )
        )

    if not results:
        print("No checks were selected.")
        return 1

    _print_results(results)

    failed = [item for item in results if item.status == "fail"]
    if failed:
        print(f"Resilience verification failed ({len(failed)} check(s)).")
        return 1

    print("Resilience verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
