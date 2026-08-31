from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import os
import shutil
import socket
import subprocess
import sys
import time

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


_RUN_E2E_ENV = "OKR_RUN_PLAYWRIGHT_SPA_E2E"

_TEST_PASSWORD = "E2E-Atlas-Password-123"
_E2E_ROLES: dict[str, tuple[str, str]] = {
    "admin": ("e2e_admin", _TEST_PASSWORD),
    "manager": ("e2e_manager", _TEST_PASSWORD),
    "member": ("e2e_member", _TEST_PASSWORD),
}


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return float(value) if value > 0 else default


def _resolve_chromium_executable() -> str | None:
    env_path = str(os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or "").strip()
    if env_path:
        if not Path(env_path).is_file():
            return None
        return env_path

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


def _npm_command() -> list[str]:
    npm_name = "npm.cmd" if os.name == "nt" else "npm"
    npm_path = shutil.which(npm_name)
    if not npm_path:
        pytest.skip(f"{npm_name} is required for SPA e2e but was not found on PATH.")
    assert npm_path is not None
    return [npm_path]


def _require_e2e_playwright_prereqs() -> None:
    chromium_path = _resolve_chromium_executable()
    if not chromium_path:
        pytest.skip(
            "Playwright SPA e2e requires a Chromium-compatible browser. "
            "Set PLAYWRIGHT_CHROMIUM_EXECUTABLE to a local Chrome/Edge binary "
            "(for example, C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe), "
            "or install one via Playwright browsers command (`playwright install chromium`) "
            "in the active Node environment."
        )


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


def _wait_for_http_and_process(
    url: str,
    process: subprocess.Popen[Any] | None,
    *,
    timeout_seconds: float,
) -> tuple[bool, int | None]:
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False, process.returncode
        try:
            with urlopen(url, timeout=1.5) as response:  # nosec B310
                status = int(getattr(response, "status", 0) or 0)
                if 200 <= status < 500:
                    return True, None
        except (URLError, OSError):
            pass
        time.sleep(0.5)
    return False, process.returncode if process is not None else None


def _terminate_process(process: subprocess.Popen[Any] | None) -> None:
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
start = now - timedelta(days=14)
end = now + timedelta(days=30)

with Session(engine, expire_on_commit=False) as session:
    admin_user = User(
        username='e2e_admin',
        password_hash=crud.hash_password('E2E-Atlas-Password-123'),
        display_name='E2E Admin',
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
        password_changed_at=now,
    )
    manager_user = User(
        username='e2e_manager',
        password_hash=crud.hash_password('E2E-Atlas-Password-123'),
        display_name='E2E Manager',
        role=UserRole.MANAGER,
        is_active=True,
        must_change_password=False,
        password_changed_at=now,
    )
    member_user = User(
        username='e2e_member',
        password_hash=crud.hash_password('E2E-Atlas-Password-123'),
        display_name='E2E Member',
        role=UserRole.MEMBER,
        is_active=True,
        must_change_password=False,
        password_changed_at=now,
    )
    session.add(admin_user)
    session.add(manager_user)
    session.flush()
    member_user.manager_id = manager_user.id
    session.add(member_user)
    session.flush()

    e2e_cycle = Cycle(
        title='E2E Core Cycle',
        start_date=start,
        end_date=end,
        is_active=True,
        owner_manager_id=None,
    )
    session.add(e2e_cycle)
    session.flush()

    admin_goal = Goal(
        owner_id=admin_user.id,
        cycle_id=e2e_cycle.id,
        title='E2E Admin Goal',
        progress=25,
        created_by='e2e_admin',
    )
    manager_goal = Goal(
        owner_id=manager_user.id,
        cycle_id=e2e_cycle.id,
        title='E2E Manager Goal',
        progress=20,
        created_by='e2e_manager',
    )
    member_goal = Goal(
        owner_id=member_user.id,
        cycle_id=e2e_cycle.id,
        title='E2E Member Goal',
        progress=15,
        created_by='e2e_member',
    )
    session.add(admin_goal)
    session.add(manager_goal)
    session.add(member_goal)
    session.flush()

    admin_objective = Objective(
        goal_id=admin_goal.id,
        title='E2E Admin Objective',
        progress=20,
        created_by='e2e_admin',
    )
    manager_objective = Objective(
        goal_id=manager_goal.id,
        title='E2E Manager Objective',
        progress=18,
        created_by='e2e_manager',
    )
    member_objective = Objective(
        goal_id=member_goal.id,
        title='E2E Member Objective',
        progress=16,
        created_by='e2e_member',
    )
    session.add(admin_objective)
    session.add(manager_objective)
    session.add(member_objective)
    session.flush()

    admin_kr = KeyResult(
        objective_id=admin_objective.id,
        title='E2E Admin Key Result',
        progress=10,
        target_value=100.0,
        current_value=10.0,
        created_by='e2e_admin',
    )
    manager_kr = KeyResult(
        objective_id=manager_objective.id,
        title='E2E Manager Key Result',
        progress=14,
        target_value=50.0,
        current_value=10.0,
        created_by='e2e_manager',
    )
    member_kr = KeyResult(
        objective_id=member_objective.id,
        title='E2E Member Key Result',
        progress=16,
        target_value=20.0,
        current_value=5.0,
        created_by='e2e_member',
    )
    session.add(admin_kr)
    session.add(manager_kr)
    session.add(member_kr)
    session.flush()

    admin_task = Task(
        key_result_id=admin_kr.id,
        title='E2E Admin Focus Task',
        progress=0,
        status=TaskStatus.TODO,
        assignee_id=admin_user.id,
        created_by='e2e_admin',
    )
    manager_task = Task(
        key_result_id=manager_kr.id,
        title='E2E Manager Focus Task',
        progress=0,
        status=TaskStatus.TODO,
        assignee_id=manager_user.id,
        created_by='e2e_manager',
    )
    member_task = Task(
        key_result_id=member_kr.id,
        title='E2E Member Focus Task',
        progress=0,
        status=TaskStatus.TODO,
        assignee_id=member_user.id,
        created_by='e2e_member',
    )
    session.add(admin_task)
    session.add(manager_task)
    session.add(member_task)
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
            f"Database seed failed.\\nstdout:\\n{result.stdout}\\nstderr:\\n{result.stderr}"
        )


@dataclass(frozen=True)
class E2EStack:
    app_url: str


@pytest.fixture(scope="module")
def e2e_stack(
    tmp_path_factory: pytest.TempPathFactory,
) -> Any:
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
    _require_e2e_playwright_prereqs()

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
                "OKR_ALEMBIC_UPGRADE_TARGET": "heads",
                "PYTHONUNBUFFERED": "1",
            }
        )

    _seed_database(repo_root, env)

    backend_log_path = tmp_dir / "backend.log"
    bff_log_path = tmp_dir / "bff.log"
    spa_log_path = tmp_dir / "spa.log"
    worker_log_path = tmp_dir / "worker.log"

    backend_process: subprocess.Popen[Any] | None = None
    bff_process: subprocess.Popen[Any] | None = None
    spa_process: subprocess.Popen[Any] | None = None
    worker_process: subprocess.Popen[Any] | None = None

    with (
        backend_log_path.open("w", encoding="utf-8") as backend_log,
        bff_log_path.open("w", encoding="utf-8") as bff_log,
        spa_log_path.open("w", encoding="utf-8") as spa_log,
        worker_log_path.open("w", encoding="utf-8") as worker_log,
    ):
        try:
            startup_timeout_backend = _env_float("OKR_E2E_BACKEND_STARTUP_TIMEOUT_SECONDS", 60.0)
            startup_timeout_bff = _env_float("OKR_E2E_BFF_STARTUP_TIMEOUT_SECONDS", 90.0)
            startup_timeout_spa = _env_float("OKR_E2E_SPA_STARTUP_TIMEOUT_SECONDS", 180.0)

            backend_process = subprocess.Popen(
                [sys.executable, "-m", "backend_app.run_api"],
                cwd=repo_root,
                env=env,
                stdout=backend_log,
                stderr=subprocess.STDOUT,
            )
            backend_ready, backend_returncode = _wait_for_http_and_process(
                f"http://127.0.0.1:{backend_port}/healthz",
                process=backend_process,
                timeout_seconds=startup_timeout_backend,
            )
            if not backend_ready:
                _terminate_process(backend_process)
                if backend_returncode is not None:
                    raise RuntimeError(
                        "Backend API exited during startup.\\n"
                        f"backend returncode={backend_returncode}\\n"
                        f"backend.log tail:\\n{_read_log_tail(backend_log_path)}"
                    )
                raise RuntimeError(
                    "Backend API did not become healthy in time.\\n"
                    f"backend.log tail:\\n{_read_log_tail(backend_log_path)}"
                )

            worker_process = subprocess.Popen(
                [sys.executable, "-m", "backend_app.worker"],
                cwd=repo_root,
                env=env,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
            )
            worker_ready, _ = _wait_for_http_and_process(
                f"http://127.0.0.1:{backend_port}/healthz",
                process=backend_process,
                timeout_seconds=5,
            )
            if not worker_ready:
                if worker_process.poll() is not None:
                    _terminate_process(worker_process)
                    raise RuntimeError(
                        "Backend worker exited during startup.\\n"
                        f"worker.log tail:\\n{_read_log_tail(worker_log_path)}"
                    )
                time.sleep(0.5)

            bff_env = env.copy()
            bff_env.update(
                {
                    "BFF_HOST": "127.0.0.1",
                    "BFF_PORT": str(bff_port),
                    "BFF_SESSION_SECRET": "e2e-session-secret-at-least-32-chars",
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
            if not _wait_for_http_and_process(
                f"http://127.0.0.1:{bff_port}/healthz",
                process=bff_process,
                timeout_seconds=startup_timeout_bff,
            ):
                _terminate_process(bff_process)
                raise RuntimeError(
                    "SPA BFF did not become healthy in time.\\n"
                    f"bff.log tail:\\n{_read_log_tail(bff_log_path)}"
                )

            spa_env = env.copy()
            spa_env.update(
                {
                    "BFF_PUBLIC_ORIGIN": f"http://127.0.0.1:{bff_port}",
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
            if not _wait_for_http_and_process(
                f"http://127.0.0.1:{app_port}/login",
                process=spa_process,
                timeout_seconds=startup_timeout_spa,
            ):
                _terminate_process(spa_process)
                raise RuntimeError(
                    "SPA Web did not become healthy in time.\\n"
                    f"spa.log tail:\\n{_read_log_tail(spa_log_path)}"
                )

            yield E2EStack(app_url=f"http://127.0.0.1:{app_port}")
        finally:
            _terminate_process(spa_process)
            _terminate_process(bff_process)
            _terminate_process(backend_process)
            _terminate_process(worker_process)


def _login(page, username: str, password: str) -> None:
    from playwright.sync_api import expect

    username_input = page.locator("#username")
    password_input = page.locator("#password")
    sign_in_button = page.get_by_role("button", name="Sign in", exact=True)
    observed_login_payload: dict[str, object] = {}

    def _capture_request(request) -> None:
        if request.url.endswith("/api/session/login") and request.method == "POST":
            try:
                observed_login_payload.update({"json": request.post_data_json})
            except Exception:
                observed_login_payload.update({"raw": request.post_data or ""})

    page.on("request", _capture_request)

    expect(username_input).to_be_visible(timeout=60_000)
    username_input.click()
    username_input.fill("")
    username_input.type(username, delay=10)
    expect(password_input).to_be_visible(timeout=60_000)
    password_input.click()
    password_input.fill("")
    password_input.type(password, delay=10)
    resolved_username = username_input.input_value()
    resolved_password = password_input.input_value()
    if resolved_username != username or resolved_password != password:
        page.evaluate(
            """
            ([user, pwd]) => {
              const usernameEl = document.querySelector("#username");
              const passwordEl = document.querySelector("#password");
              if (usernameEl) {
                usernameEl.value = String(user || "");
                usernameEl.dispatchEvent(new Event("input", { bubbles: true }));
              }
              if (passwordEl) {
                passwordEl.value = String(pwd || "");
                passwordEl.dispatchEvent(new Event("input", { bubbles: true }));
              }
            }
            """,
            [username, password],
        )
        page.wait_for_timeout(100)
        resolved_username = username_input.input_value()
        resolved_password = password_input.input_value()
        if resolved_username != username or resolved_password != password:
            raise AssertionError(
                f"Failed to populate login fields. Observed username={resolved_username!r}, "
                f"password={resolved_password!r}"
            )
    for _ in range(5):
        if sign_in_button.is_enabled():
            break
        page.wait_for_timeout(200)
    sign_in_button.click()
    if not observed_login_payload:
        raise AssertionError("Login request payload was not observed.")
    request_payload = observed_login_payload.get("json")
    if isinstance(request_payload, dict):
        assert (
            str(request_payload.get("username", "")) == username
        ), f"Sent username mismatch: {request_payload.get('username')!r} != {username!r}"
        assert (
            str(request_payload.get("password", "")) == password
        ), f"Sent password mismatch: {request_payload.get('password')!r}"
    expect(page.get_by_role("button", name="Sign out", exact=True)).to_be_visible(
        timeout=90_000
    )


def _run_timer_path(page) -> None:
    from playwright.sync_api import expect

    active_task_select = page.locator("#focus-task-ref")
    timer_start_events: list[dict[str, object]] = []
    timer_stop_events: list[dict[str, object]] = []

    def _capture_timer_response(response) -> None:
        url = str(response.url or "")
        if "/api/backend/v1/timer/start" in url:
            timer_start_events.append(
                {
                    "status": response.status,
                    "status_text": str(response.status_text),
                    "url": url,
                }
            )
        elif "/api/backend/v1/timer/stop" in url:
            timer_stop_events.append(
                {
                    "status": response.status,
                    "status_text": str(response.status_text),
                    "url": url,
                }
            )

    page.on("response", _capture_timer_response)

    expect(active_task_select).to_be_visible(timeout=90_000)
    page.wait_for_function(
        "() => (document.querySelectorAll('#focus-task-ref option') || []).length >= 1",
        timeout=90_000,
    )

    start_button = page.get_by_role("button", name="Start timer", exact=True)
    expect(start_button).to_be_visible(timeout=90_000)

    fallback_cycle_hinted = False
    valid_task_indices: list[int] = []
    option_count = 0
    for _ in range(240):
        option_count = active_task_select.locator("option").count()
        if option_count < 1:
            page.wait_for_timeout(250)
            continue
        valid_task_indices = []
        for option_index in range(option_count):
            option = active_task_select.locator("option").nth(option_index)
            option_value = option.get_attribute("value") or ""
            option_label = (option.text_content() or "").strip().lower()
            if option_value and option_label != "none":
                valid_task_indices.append(option_index)
        if valid_task_indices:
            break

        if option_count == 1 and not fallback_cycle_hinted:
            page.goto(
                f"{page.url.split('?')[0].rstrip('/')}/?cycle=1&sel=goal_1",
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            fallback_cycle_hinted = True
            page.wait_for_timeout(1_000)
        else:
            page.wait_for_timeout(500)

    if option_count < 1:
        pytest.fail(
            "Active Task selector has no option elements after login; cannot start timer."
        )
    if not valid_task_indices:
        options_snapshot = []
        try:
            for option_index in range(option_count):
                option = active_task_select.locator("option").nth(option_index)
                value = option.get_attribute("value") or ""
                label = option.text_content() or ""
                options_snapshot.append(f"{option_index}:{value}:{label.strip()}")
        except Exception:
            options_snapshot = ["<unavailable>"]
        raise AssertionError(
            "Active Task selector has no task values; cannot start timer. "
            f"Options seen: {options_snapshot!r}"
        )

    active_task_select.select_option(index=valid_task_indices[0])
    expect(start_button).to_be_enabled(timeout=90_000)

    timer_started = False
    last_start_status = "not-started"
    timer_dialog = page.get_by_role("dialog", name="Focus timer session")
    timer_error_locator = page.locator("text=/timer/i")
    for option_index in valid_task_indices:
        active_task_select.select_option(index=option_index)
        page.wait_for_timeout(150)
        try:
            expect(start_button).to_be_enabled(timeout=1_000)
        except Exception:
            continue
        start_button.click()
        if timer_start_events:
            last_start_status = str(timer_start_events[-1].get("status", "no-status"))
        if last_start_status != "404":
            try:
                expect(timer_dialog).to_be_visible(timeout=1_500)
                timer_started = True
                break
            except Exception:
                pass
        page.wait_for_timeout(250)
        if timer_error_locator.count() > 0 and timer_error_locator.first.is_visible():
            page.keyboard.press("Escape")

    if not timer_started:
        start_options = []
        try:
            for option_index in range(option_count):
                option = active_task_select.locator("option").nth(option_index)
                value = option.get_attribute("value") or ""
                label = option.text_content() or ""
                start_options.append(f"{option_index}:{value}:{label}")
        except Exception:
            pass
        last_start = timer_start_events[-1] if timer_start_events else {}
        last_stop = timer_stop_events[-1] if timer_stop_events else {}
        last_timer_error_message = ""
        try:
            last_timer_error_message = timer_error_locator.first.text_content() or ""
        except Exception:
            last_timer_error_message = ""
        start_msg = str(last_start.get("status", "no-request"))
        stop_msg = str(last_stop.get("status", "no-request"))
        raise AssertionError(
            "Could not start timer for any visible task option. "
            f"Last timer start status={start_msg}, stop status={stop_msg}, "
            f"start message={last_start_status}, options={start_options}. "
            f"Last timer error text={last_timer_error_message!r}"
        )

    timer_dialog = page.get_by_role("dialog", name="Focus timer session")
    expect(timer_dialog).to_be_visible(timeout=90_000)
    timer_dialog.get_by_role("button", name="Close", exact=True).click()
    expect(timer_dialog).not_to_be_visible(timeout=90_000)


def _run_check_in_path(page) -> None:
    from playwright.sync_api import expect

    page.get_by_role("button", name="Check-In").click()
    expect(page.get_by_role("button", name="2. Check-Ins", exact=True)).to_be_visible(
        timeout=90_000
    )
    page.get_by_role("button", name="2. Check-Ins", exact=True).click()
    submit_checkins = page.get_by_role("button", name="Submit Check-In")
    all_clear_message = page.get_by_text("All clear for this cycle.")
    if submit_checkins.count() > 0:
        submit_checkins.first.click()
        metric_inputs = page.locator('input[placeholder^="e.g."]').first
        if metric_inputs.count() > 0:
            metric_inputs.fill("10")
            submit_checkins.first.click()
        expect(submit_checkins.first).to_have_text("Submit Check-In", timeout=90_000)
    else:
        expect(all_clear_message).to_be_visible(timeout=90_000)


def _run_weekly_job_path(page) -> None:
    from playwright.sync_api import expect
    job_events: list[dict[str, object]] = []

    def _capture_job_response(response) -> None:
        url = str(response.url or "")
        if "/api/backend/v1/jobs" in url:
            job_events.append(
                {
                    "status": response.status,
                    "status_text": str(response.status_text),
                    "url": url,
                }
            )

    page.get_by_role("button", name="Weekly Report").click()
    weekly_pdf = page.get_by_role("button", name="Export Weekly PDF")
    expect(weekly_pdf).to_be_visible(timeout=90_000)
    expect(weekly_pdf).to_be_enabled(timeout=90_000)

    page.on("response", _capture_job_response)
    weekly_pdf.click()
    try:
        expect(weekly_pdf).to_have_text("Exporting...", timeout=15_000)
    except Exception:
        try:
            expect(weekly_pdf).to_have_text("PDF export unavailable; downloaded HTML fallback.", timeout=1_000)
        except Exception:
            pass

    page.wait_for_timeout(1_000)
    if not job_events:
        raise AssertionError(
            "No weekly job response observed after clicking Export Weekly PDF. "
            "If this mode does not use backend job API in current build, capture backend path explicitly."
        )
    last_event = job_events[-1]
    if int(last_event.get("status", 0)) >= 400:
        raise AssertionError(
            f"Weekly export request failed with status={last_event.get('status')}, "
            f"url={last_event.get('url')}, status_text={last_event.get('status_text')}"
        )

    fallback_error = page.locator("text=PDF export unavailable; downloaded HTML fallback.")
    if fallback_error.count() > 0:
        expect(fallback_error).to_be_visible(timeout=1_000)


def _run_admin_mutation_path(page) -> None:
    from playwright.sync_api import expect

    page.get_by_role("button", name="Admin").click()
    expect(page.get_by_role("heading", name="Platform Controls")).to_be_visible(timeout=90_000)
    page.get_by_role("button", name="Cycles").click()
    page.get_by_placeholder("Cycle title (example: Q1-2026)").fill(
        f"E2E Cycle {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )

    date_inputs = page.locator("input[type='date']")
    expect(date_inputs).to_have_count(2, timeout=20_000)
    start_day = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    end_day = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%d")
    date_inputs.first.fill(start_day)
    date_inputs.nth(1).fill(end_day)

    owner_select = page.locator("select").filter(
        has_text="Select cycle owner (manager/admin)"
    )
    expect(owner_select).to_be_visible(timeout=20_000)
    owner_select.select_option(label="E2E Admin")
    page.get_by_role("button", name="Create cycle").click()
    expect(page.get_by_text("Cycle created.")).to_be_visible(timeout=90_000)


@pytest.mark.parametrize(
    ("role"),
    ["admin", "manager", "member"],
    ids=["admin", "manager", "member"],
)
def test_role_based_spa_critical_paths(e2e_stack: E2EStack, role: str) -> None:
    from playwright.sync_api import Error, expect, sync_playwright
    chromium_path = _resolve_chromium_executable()
    launch_kwargs: dict[str, object] = {"headless": True}
    if chromium_path:
        launch_kwargs["executable_path"] = chromium_path
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**launch_kwargs)
        except Error as exc:
            if chromium_path:
                pytest.skip(
                    "Playwright could not launch Chromium using local executable. "
                    f"Details: {exc}. Path: {chromium_path}"
                )
            pytest.skip(
                "Chromium runtime is unavailable for Playwright. "
                "Install browsers via `playwright install chromium` or set "
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE to a local Chrome path. "
                f"Details: {exc}"
            )

        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        username, password = _E2E_ROLES[role]
        page.goto(f"{e2e_stack.app_url}/login", wait_until="domcontentloaded", timeout=90_000)

        _login(page, username=username, password=password)
        _run_timer_path(page)
        _run_check_in_path(page)
        _run_weekly_job_path(page)

        if role == "admin":
            _run_admin_mutation_path(page)
        else:
            expect(page.get_by_role("button", name="Admin")).to_have_count(0, timeout=10_000)
            expect(page.get_by_role("button", name="Admin")).to_have_count(0, timeout=10_000)

        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible(
            timeout=90_000
        )

        context.close()
        browser.close()
