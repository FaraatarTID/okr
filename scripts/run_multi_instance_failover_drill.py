#!/usr/bin/env python3
"""Run a local multi-instance failover drill for resilience verification."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
STREAMLIT_APP_DIR = ROOT / "streamlit_app"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


class ManagedProcess:
    """Subprocess wrapper with log capture."""

    def __init__(
        self, *, name: str, argv: list[str], env: dict[str, str], log_path: Path
    ):
        self.name = str(name)
        self.argv = list(argv)
        self.env = dict(env)
        self.log_path = Path(log_path)
        self.process = subprocess.Popen(  # noqa: S603 - command is controlled
            self.argv,
            cwd=ROOT,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._pump = Thread(target=self._pump_output, daemon=True)
        self._pump.start()

    def _pump_output(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w", encoding="utf-8") as handle:
            if self.process.stdout is None:
                return
            for line in self.process.stdout:
                handle.write(line)
                handle.flush()

    def terminate(self, *, timeout_seconds: float = 8.0) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout_seconds)


def _http_status(url: str, *, timeout_seconds: float = 3.0) -> int | None:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - local drill URLs
            return int(getattr(response, "status", 0) or 0)
    except Exception:
        return None


def _wait_for_http(urls: list[str], *, timeout_seconds: float) -> tuple[bool, str]:
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        for url in urls:
            status = _http_status(url)
            if status == 200:
                return True, url
        time.sleep(0.5)
    return False, urls[0] if urls else ""


def _fetch_url(url: str, *, timeout_seconds: float = 5.0) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - local drill URLs
            status = int(getattr(response, "status", 0) or 0)
            return status == 200, f"HTTP {status}"
    except URLError as exc:
        return False, str(exc)
    except Exception as exc:  # broad by design for operator drill output
        return False, str(exc)


def _bootstrap_streamlit_src() -> None:
    streamlit_src = str(STREAMLIT_APP_DIR.resolve())
    if streamlit_src not in sys.path:
        sys.path.insert(0, streamlit_src)


def _broadcast_invalidation(*, actor_username: str) -> tuple[bool, int, int]:
    _bootstrap_streamlit_src()
    from src.services import distributed_state_service

    before = int(distributed_state_service.get_last_invalidation_timestamp() or 0)
    ok = bool(
        distributed_state_service.broadcast_cache_invalidation(
            actor_username=actor_username
        )
    )
    after = int(distributed_state_service.get_last_invalidation_timestamp() or 0)
    return ok, before, after


def _build_env(
    *,
    database_url: str,
    backend_port: int,
    service_token: str,
    signing_secret: str,
) -> dict[str, str]:
    env = dict(os.environ)
    env["OKR_DATABASE_URL"] = str(database_url)
    env["OKR_BACKEND_API_URL"] = f"http://127.0.0.1:{int(backend_port)}"
    env["OKR_BACKEND_SERVICE_TOKEN"] = str(service_token)
    env["OKR_BACKEND_SIGNING_SECRET"] = str(signing_secret)
    env["OKR_BACKEND_ENFORCE_TOKEN"] = "true"
    env["OKR_BACKEND_ENFORCE_REQUEST_SIGNING"] = "true"
    env["OKR_BACKEND_SECURITY_STATE_BACKEND"] = "database"
    return env


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local backend + dual Streamlit failover drill."
    )
    parser.add_argument("--backend-port", type=int, default=8100)
    parser.add_argument("--streamlit-a-port", type=int, default=8501)
    parser.add_argument("--streamlit-b-port", type=int, default=8502)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--actor", default="system")
    parser.add_argument("--service-token", default="local-drill-service-token")
    parser.add_argument("--signing-secret", default="local-drill-signing-secret")
    parser.add_argument(
        "--artifact-dir",
        default="",
        help="Directory for logs/db artifact. Defaults to temporary directory.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep generated logs and sqlite DB after the drill.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    artifact_dir = (
        Path(args.artifact_dir).resolve()
        if str(args.artifact_dir).strip()
        else Path(tempfile.mkdtemp(prefix="okr_failover_drill_"))
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    db_path = artifact_dir / "drill.sqlite3"
    database_url = f"sqlite:///{db_path.as_posix()}"

    env = _build_env(
        database_url=database_url,
        backend_port=int(args.backend_port),
        service_token=str(args.service_token),
        signing_secret=str(args.signing_secret),
    )
    os.environ.update(
        {
            "OKR_DATABASE_URL": env["OKR_DATABASE_URL"],
            "OKR_BACKEND_API_URL": env["OKR_BACKEND_API_URL"],
            "OKR_BACKEND_SERVICE_TOKEN": env["OKR_BACKEND_SERVICE_TOKEN"],
            "OKR_BACKEND_SIGNING_SECRET": env["OKR_BACKEND_SIGNING_SECRET"],
        }
    )

    backend = ManagedProcess(
        name="backend",
        argv=[sys.executable, "-m", "backend_app.run_api"],
        env=env,
        log_path=artifact_dir / "backend.log",
    )
    streamlit_a: ManagedProcess | None = None
    streamlit_b: ManagedProcess | None = None
    results: list[CheckResult] = []

    try:
        backend_ok, backend_url = _wait_for_http(
            [f"http://127.0.0.1:{int(args.backend_port)}/healthz"],
            timeout_seconds=float(args.timeout_seconds),
        )
        results.append(
            CheckResult(
                name="backend_health",
                status="pass" if backend_ok else "fail",
                detail=f"{backend_url} {'ready' if backend_ok else 'not ready'}",
            )
        )
        if not backend_ok:
            return _finish(results, artifact_dir=artifact_dir, keep_artifacts=True)

        streamlit_argv_common = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_app/app.py",
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
            "--logger.level",
            "info",
        ]
        streamlit_a = ManagedProcess(
            name="streamlit_a",
            argv=[
                *streamlit_argv_common,
                "--server.port",
                str(int(args.streamlit_a_port)),
            ],
            env=env,
            log_path=artifact_dir / "streamlit_a.log",
        )
        streamlit_b = ManagedProcess(
            name="streamlit_b",
            argv=[
                *streamlit_argv_common,
                "--server.port",
                str(int(args.streamlit_b_port)),
            ],
            env=env,
            log_path=artifact_dir / "streamlit_b.log",
        )

        a_ok, a_url = _wait_for_http(
            [
                f"http://127.0.0.1:{int(args.streamlit_a_port)}/_stcore/health",
                f"http://127.0.0.1:{int(args.streamlit_a_port)}/healthz",
            ],
            timeout_seconds=float(args.timeout_seconds),
        )
        b_ok, b_url = _wait_for_http(
            [
                f"http://127.0.0.1:{int(args.streamlit_b_port)}/_stcore/health",
                f"http://127.0.0.1:{int(args.streamlit_b_port)}/healthz",
            ],
            timeout_seconds=float(args.timeout_seconds),
        )
        results.extend(
            [
                CheckResult(
                    name="streamlit_a_health",
                    status="pass" if a_ok else "fail",
                    detail=f"{a_url} {'ready' if a_ok else 'not ready'}",
                ),
                CheckResult(
                    name="streamlit_b_health",
                    status="pass" if b_ok else "fail",
                    detail=f"{b_url} {'ready' if b_ok else 'not ready'}",
                ),
            ]
        )
        if not (a_ok and b_ok):
            return _finish(results, artifact_dir=artifact_dir, keep_artifacts=True)

        _fetch_url(f"http://127.0.0.1:{int(args.streamlit_a_port)}/")
        _fetch_url(f"http://127.0.0.1:{int(args.streamlit_b_port)}/")

        broadcast_ok, before_ts, after_ts = _broadcast_invalidation(
            actor_username=str(args.actor).strip() or "system"
        )
        results.append(
            CheckResult(
                name="distributed_invalidation_signal",
                status=(
                    "pass"
                    if broadcast_ok and int(after_ts) > int(before_ts)
                    else "fail"
                ),
                detail=(
                    f"broadcast_ok={broadcast_ok}, before={before_ts}, after={after_ts}"
                ),
            )
        )

        a_after_ok, a_after_detail = _fetch_url(
            f"http://127.0.0.1:{int(args.streamlit_a_port)}/?drill=after_invalidation_a"
        )
        b_after_ok, b_after_detail = _fetch_url(
            f"http://127.0.0.1:{int(args.streamlit_b_port)}/?drill=after_invalidation_b"
        )
        results.extend(
            [
                CheckResult(
                    name="streamlit_a_after_invalidation_http",
                    status="pass" if a_after_ok else "fail",
                    detail=a_after_detail,
                ),
                CheckResult(
                    name="streamlit_b_after_invalidation_http",
                    status="pass" if b_after_ok else "fail",
                    detail=b_after_detail,
                ),
            ]
        )

        query_payload = urlencode(
            {
                "cycle": "1",
                "mode": "Weekly",
                "focus": "task_1",
                "nav": "goal_1,task_1",
                "sel": "task_1",
                "scope": "My OKRs",
                "ft": "task_1",
                "jump": "drill",
                "lens": "Scope",
            }
        )
        drill_url_on_a = (
            f"http://127.0.0.1:{int(args.streamlit_a_port)}/?{query_payload}"
        )
        on_a_ok, on_a_detail = _fetch_url(drill_url_on_a)
        results.append(
            CheckResult(
                name="url_context_request_on_instance_a",
                status="pass" if on_a_ok else "fail",
                detail=on_a_detail,
            )
        )

        streamlit_a.terminate()
        on_b_ok, on_b_detail = _fetch_url(
            f"http://127.0.0.1:{int(args.streamlit_b_port)}/?{query_payload}"
        )
        results.append(
            CheckResult(
                name="url_context_request_on_instance_b_after_a_stop",
                status="pass" if on_b_ok else "fail",
                detail=on_b_detail,
            )
        )

        keep = bool(args.keep_artifacts)
        return _finish(results, artifact_dir=artifact_dir, keep_artifacts=keep)
    finally:
        if streamlit_a is not None:
            streamlit_a.terminate()
        if streamlit_b is not None:
            streamlit_b.terminate()
        backend.terminate()


def _finish(
    results: list[CheckResult], *, artifact_dir: Path, keep_artifacts: bool
) -> int:
    failures = [result for result in results if result.status == "fail"]
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.detail}")

    if failures:
        print(
            "Multi-instance failover drill failed. "
            f"Artifacts kept at: {artifact_dir.as_posix()}"
        )
        return 1

    print("Multi-instance failover drill passed.")
    if keep_artifacts:
        print(f"Artifacts kept at: {artifact_dir.as_posix()}")
    else:
        shutil.rmtree(artifact_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
