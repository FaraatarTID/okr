from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest


_RUN_E2E_ENV = "OKR_RUN_PLAYWRIGHT_SPA_E2E"
_TEST_USERNAME = "e2e_admin"
_TEST_PASSWORD = "E2E-Atlas-Password-123"


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _npm_command() -> list[str]:
    npm_name = "npm.cmd" if os.name == "nt" else "npm"
    npm_path = shutil.which(npm_name)
    if not npm_path:
        pytest.skip(f"{npm_name} is required for SPA e2e but was not found on PATH.")
    return [npm_path]


def _wait_for_http(url: str, *, timeout_seconds: float) -> bool:
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.5) as response:  # nosec B310
                status = int(getattr(response, "status", 0) or 0)
                if 200 <= status < 500:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def _terminate_process(process: subprocess.Popen[object] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _read_log_tail(path: Path, *, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _seed_database(repo_root: Path, env: dict[str, str]) -> None:
    script = """
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

import src.crud as crud
import src.database as database
from src.models import Cycle, Goal, KeyResult, Objective, Task, TaskStatus, User, UserRole

database.DATABASE_URL = None
database._engine = None
database._migrations_applied_urls.clear()
database.init_database()
engine = database.get_engine()

now = datetime.now(timezone.utc).replace(tzinfo=None)
with Session(engine, expire_on_commit=False) as session:
    user = User(
        username='e2e_admin',
        password_hash=crud.hash_password('E2E-Atlas-Password-123'),
        display_name='E2E Admin',
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
        password_changed_at=now,
    )
    session.add(user)
    session.flush()

    cycle = Cycle(
        title='E2E Cycle',
        start_date=now - timedelta(days=14),
        end_date=now + timedelta(days=30),
        is_active=True,
    )
    session.add(cycle)
    session.flush()

    goal = Goal(
        owner_id=user.id,
        cycle_id=cycle.id,
        title='E2E Goal',
        progress=25,
        created_by='e2e_admin',
    )
    session.add(goal)
    session.flush()

    objective = Objective(
        goal_id=goal.id,
        title='E2E Objective',
        progress=20,
        created_by='e2e_admin',
    )
    session.add(objective)
    session.flush()

    key_result = KeyResult(
        objective_id=objective.id,
        title='E2E Key Result',
        progress=10,
        target_value=100.0,
        current_value=10.0,
        created_by='e2e_admin',
    )
    session.add(key_result)
    session.flush()

    task = Task(
        key_result_id=key_result.id,
        title='E2E Focus Task',
        progress=0,
        status=TaskStatus.TODO,
        assignee_id=user.id,
        created_by='e2e_admin',
    )
    session.add(task)
    session.commit()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Database seed failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


@dataclass(frozen=True)
class E2EStack:
    app_url: str
    username: str
    password: str


@pytest.fixture(scope="module")
def e2e_stack(tmp_path_factory: pytest.TempPathFactory) -> E2EStack:
    if not _truthy(os.getenv(_RUN_E2E_ENV)):
        pytest.skip(
            f"Playwright SPA e2e is disabled. Set {_RUN_E2E_ENV}=1 to run this test."
        )

    pytest.importorskip(
        "playwright.sync_api",
        reason=(
            "Playwright is not installed in this environment. "
            "Install dependencies and run `playwright install chromium`."
        ),
    )

    repo_root = Path(__file__).resolve().parents[1]
    tmp_dir = tmp_path_factory.mktemp("playwright_spa_e2e")
    db_path = tmp_dir / "playwright_spa_e2e.sqlite3"
    db_url = f"sqlite:///{db_path.as_posix()}"
    backend_port = _free_local_port()
    bff_port = _free_local_port()
    app_port = _free_local_port()
    service_token = "e2e-service-token"

    env = os.environ.copy()
    existing_pythonpath = str(env.get("PYTHONPATH", "")).strip()
    pythonpath_parts = [str(repo_root)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env.update(
        {
            "OKR_DATABASE_URL": db_url,
            "DATABASE_URL": db_url,
            "OKR_ALLOW_NON_SUPABASE_DB": "true",
            "OKR_ENV": "development",
            "ALLOW_EXTERNAL_AI": "false",
            "OKR_BACKEND_API_URL": f"http://127.0.0.1:{backend_port}",
            "OKR_BACKEND_HOST": "127.0.0.1",
            "OKR_BACKEND_PORT": str(backend_port),
            "OKR_BACKEND_SERVICE_TOKEN": service_token,
            "OKR_BACKEND_ENFORCE_TOKEN": "true",
            "OKR_BACKEND_ENFORCE_REQUEST_SIGNING": "false",
            "PYTHONUNBUFFERED": "1",
        }
    )

    _seed_database(repo_root, env)

    backend_log_path = tmp_dir / "backend.log"
    bff_log_path = tmp_dir / "bff.log"
    spa_log_path = tmp_dir / "spa.log"
    backend_process: subprocess.Popen[object] | None = None
    bff_process: subprocess.Popen[object] | None = None
    spa_process: subprocess.Popen[object] | None = None

    with (
        backend_log_path.open("w", encoding="utf-8") as backend_log,
        bff_log_path.open("w", encoding="utf-8") as bff_log,
        spa_log_path.open("w", encoding="utf-8") as spa_log,
    ):
        try:
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "backend_app.run_api"],
                cwd=repo_root,
                env=env,
                stdout=backend_log,
                stderr=subprocess.STDOUT,
            )
            if not _wait_for_http(
                f"http://127.0.0.1:{backend_port}/healthz",
                timeout_seconds=60,
            ):
                _terminate_process(backend_process)
                backend_log.flush()
                raise RuntimeError(
                    "Backend API did not become healthy in time.\n"
                    f"backend.log tail:\n{_read_log_tail(backend_log_path)}"
                )

            bff_env = env.copy()
            bff_env.update(
                {
                    "BFF_HOST": "127.0.0.1",
                    "BFF_PORT": str(bff_port),
                    "BFF_SESSION_SECRET": "e2e-session-secret",
                    "BFF_SESSION_TTL_SECONDS": "28800",
                    "BFF_COOKIE_SECURE": "false",
                    "OKR_BACKEND_API_URL": f"http://127.0.0.1:{backend_port}",
                    "OKR_BACKEND_SERVICE_TOKEN": service_token,
                    "OKR_BACKEND_SIGNING_SECRET": "",
                    "BFF_REQUEST_TIMEOUT_MS": "20000",
                }
            )
            bff_process = subprocess.Popen(
                [*_npm_command(), "run", "dev"],
                cwd=repo_root / "spa-bff",
                env=bff_env,
                stdout=bff_log,
                stderr=subprocess.STDOUT,
            )
            if not _wait_for_http(
                f"http://127.0.0.1:{bff_port}/healthz",
                timeout_seconds=90,
            ):
                _terminate_process(bff_process)
                bff_log.flush()
                raise RuntimeError(
                    "SPA BFF did not become healthy in time.\n"
                    f"bff.log tail:\n{_read_log_tail(bff_log_path)}"
                )

            spa_env = env.copy()
            spa_env.update(
                {
                    "BFF_PUBLIC_ORIGIN": f"http://127.0.0.1:{bff_port}",
                    "OKR_SPA_ROLLOUT_ENABLED": "true",
                    "OKR_SPA_ROLLOUT_ALLOW_ALL": "true",
                    "OKR_SPA_ROLLOUT_ALLOW_PREVIEW_BYPASS": "false",
                }
            )
            spa_process = subprocess.Popen(
                [
                    *_npm_command(),
                    "run",
                    "dev",
                    "--",
                    "--port",
                    str(app_port),
                    "--hostname",
                    "127.0.0.1",
                ],
                cwd=repo_root / "spa-web",
                env=spa_env,
                stdout=spa_log,
                stderr=subprocess.STDOUT,
            )

            if not _wait_for_http(
                f"http://127.0.0.1:{app_port}/login",
                timeout_seconds=180,
            ):
                _terminate_process(spa_process)
                spa_log.flush()
                raise RuntimeError(
                    "SPA Web did not become healthy in time.\n"
                    f"spa.log tail:\n{_read_log_tail(spa_log_path)}"
                )

            yield E2EStack(
                app_url=f"http://127.0.0.1:{app_port}",
                username=_TEST_USERNAME,
                password=_TEST_PASSWORD,
            )
        finally:
            _terminate_process(spa_process)
            _terminate_process(bff_process)
            _terminate_process(backend_process)


def test_login_navigate_atlas_map_and_start_timer(e2e_stack: E2EStack) -> None:
    from playwright.sync_api import Error, expect, sync_playwright

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Error as exc:
            pytest.skip(
                "Chromium runtime is unavailable for Playwright. "
                f"Run `playwright install chromium`. Details: {exc}"
            )

        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        page.goto(f"{e2e_stack.app_url}/login", wait_until="domcontentloaded", timeout=90_000)

        username_input = page.get_by_label("Username", exact=True)
        password_input = page.get_by_label("Password", exact=True)
        sign_in_button = page.get_by_role("button", name="Sign in", exact=True)

        expect(username_input).to_be_visible(timeout=60_000)
        username_input.click()
        username_input.fill("")
        username_input.type(e2e_stack.username, delay=15)

        expect(password_input).to_be_visible(timeout=60_000)
        password_input.click()
        password_input.fill("")
        password_input.type(e2e_stack.password, delay=15)

        expect(sign_in_button).to_be_enabled(timeout=60_000)
        sign_in_button.click()

        expect(page.get_by_role("button", name="Logout").first).to_be_visible(timeout=90_000)

        use_suggested_button = page.get_by_role("button", name="Use Suggested").first
        if use_suggested_button.count() > 0 and use_suggested_button.is_visible():
            use_suggested_button.click()

        start_button = page.get_by_role("button", name="Start").first
        expect(start_button).to_be_visible(timeout=90_000)
        expect(start_button).to_be_enabled(timeout=90_000)
        start_button.click()
        expect(page.get_by_role("button", name="Stop & Log").first).to_be_visible(
            timeout=90_000
        )

        page.get_by_role("button", name="Logout").first.click()
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible(
            timeout=90_000
        )

        context.close()
        browser.close()
