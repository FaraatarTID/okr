from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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

    admin_cycle = Cycle(
        title='E2E Admin Cycle',
        start_date=start,
        end_date=end,
        is_active=True,
        owner_manager_id=None,
    )
    manager_cycle = Cycle(
        title='E2E Manager Cycle',
        start_date=start,
        end_date=end,
        is_active=True,
        owner_manager_id=manager_user.id,
    )
    session.add(admin_cycle)
    session.add(manager_cycle)
    session.flush()

    admin_goal = Goal(
        owner_id=admin_user.id,
        cycle_id=admin_cycle.id,
        title='E2E Admin Goal',
        progress=25,
        created_by='e2e_admin',
    )
    manager_goal = Goal(
        owner_id=manager_user.id,
        cycle_id=manager_cycle.id,
        title='E2E Manager Goal',
        progress=20,
        created_by='e2e_manager',
    )
    session.add(admin_goal)
    session.add(manager_goal)
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
    session.add(admin_objective)
    session.add(manager_objective)
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
    session.add(admin_kr)
    session.add(manager_kr)
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
        key_result_id=manager_kr.id,
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
            if not _wait_for_http(f"http://127.0.0.1:{backend_port}/healthz", timeout_seconds=5):
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
            if not _wait_for_http(
                f"http://127.0.0.1:{bff_port}/healthz",
                timeout_seconds=90,
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
            if not _wait_for_http(
                f"http://127.0.0.1:{app_port}/login",
                timeout_seconds=180,
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

    username_input = page.get_by_label("Username", exact=True)
    password_input = page.get_by_label("Password", exact=True)
    sign_in_button = page.get_by_role("button", name="Sign in", exact=True)

    expect(username_input).to_be_visible(timeout=60_000)
    username_input.click()
    username_input.fill("")
    username_input.type(username, delay=15)
    expect(password_input).to_be_visible(timeout=60_000)
    password_input.click()
    password_input.fill("")
    password_input.type(password, delay=15)
    expect(sign_in_button).to_be_enabled(timeout=60_000)
    sign_in_button.click()
    expect(page.get_by_role("button", name="Sign out", exact=True)).to_be_visible(
        timeout=90_000
    )


def _run_timer_path(page) -> None:
    from playwright.sync_api import expect

    active_task_select = page.locator("#focus-task-ref")
    expect(active_task_select).to_be_visible(timeout=90_000)
    page.wait_for_function(
        "() => (document.querySelectorAll('#focus-task-ref option') || []).length >= 2",
        timeout=90_000,
    )
    option_count = active_task_select.locator("option").count()
    if option_count < 2:
        pytest.fail(
            "Active Task selector has no task options after login; cannot start timer."
        )
    active_task_select.select_option(index=1)

    start_button = page.get_by_role("button", name="Start timer", exact=True)
    expect(start_button).to_be_visible(timeout=90_000)
    expect(start_button).to_be_enabled(timeout=90_000)
    start_button.click()
    expect(
        page.get_by_role("button", name="Stop timer + save log", exact=True)
    ).to_be_visible(timeout=90_000)

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
    expect(page.get_by_role("button", name="Submit Check-In")).to_be_visible(timeout=90_000)
    page.get_by_role("button", name="Submit Check-In").first.click()
    expect(page.get_by_text("Check-in saved.")).to_be_visible(timeout=90_000)


def _run_weekly_job_path(page) -> None:
    from playwright.sync_api import expect

    page.get_by_role("button", name="Weekly Report").click()
    weekly_pdf = page.get_by_role("button", name="Export Weekly PDF")
    expect(weekly_pdf).to_be_visible(timeout=90_000)
    expect(weekly_pdf).to_be_enabled(timeout=90_000)
    weekly_pdf.click()
    expect(weekly_pdf).to_have_text("Exporting...", timeout=90_000)
    expect(weekly_pdf).to_have_text("Export Weekly PDF", timeout=180_000)
    fallback_error = page.locator("text=PDF export unavailable; downloaded HTML fallback.")
    if fallback_error.count() > 0:
        expect(fallback_error).to_be_visible(timeout=1_000)


def _run_admin_mutation_path(page) -> None:
    from playwright.sync_api import expect

    page.get_by_role("button", name="Admin").click()
    expect(page.get_by_role("heading", name="Platform Controls")).to_be_visible(timeout=90_000)
    page.get_by_role("button", name="Cycles").click()
    page.get_by_placeholder("Cycle title (example: Q1-2026)").fill(
        f"E2E Cycle {datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    )

    date_inputs = page.locator("input[type='date']")
    expect(date_inputs).to_have_count(2, timeout=20_000)
    start_day = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    end_day = (datetime.utcnow() + timedelta(days=6)).strftime("%Y-%m-%d")
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
            expect(page.get_by_text("Cycle is managed by your manager/admin.")).to_be_visible(
                timeout=20_000
            )

        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible(
            timeout=90_000
        )

        context.close()
        browser.close()
