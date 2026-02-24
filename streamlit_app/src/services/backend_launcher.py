"""
Backend launcher service for embedded/auto mode.

This module is responsible for starting the backend API as a background
subprocess when running in Streamlit Cloud or when `OKR_BACKEND_API_URL`
is set to 'auto'. It also handles the case where the URL points to localhost,
which on Streamlit Cloud means the backend should be self-hosted.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time

_LOGGER = logging.getLogger(__name__)

# Sentinel to prevent re-running the launcher on every Streamlit rerun.
# Streamlit re-executes the entire script on interaction; we only want to
# launch once per process lifetime.
_BACKEND_LAUNCH_ATTEMPTED = False


def is_port_open(host: str, port: int, *, timeout: float = 0.5) -> bool:
    """Check if a TCP port is open on a host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def _is_localhost_url(url: str) -> bool:
    """Return True if the URL targets localhost / 127.0.0.1."""
    url_lower = url.lower()
    return (
        url_lower.startswith("http://localhost")
        or url_lower.startswith("http://127.0.0.1")
        or url_lower.startswith("https://localhost")
        or url_lower.startswith("https://127.0.0.1")
    )


def _parse_host_port_from_url(url: str, default_port: int = 8100) -> tuple[str, int]:
    """Extract host and port from a URL like http://localhost:8100."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or default_port
        return host, port
    except Exception:
        return "127.0.0.1", default_port


def _find_repo_root() -> str | None:
    """Walk up from this file's location to find the repo root (contains backend_app/)."""
    file_dir = os.path.dirname(os.path.abspath(__file__))
    # backend_launcher.py lives at: <repo>/streamlit_app/src/services/
    # Walk up up to 4 levels looking for "backend_app"
    candidate = file_dir
    for _ in range(5):
        if os.path.isdir(os.path.join(candidate, "backend_app")):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    return None


def ensure_backend_running() -> bool:
    """
    Ensure the embedded backend API is running.

    Triggers embedded startup when:
    1. ``OKR_BACKEND_API_URL`` is the literal string ``"auto"``.
    2. ``OKR_BACKEND_API_URL`` is empty AND we are on Streamlit Cloud.
    3. ``OKR_BACKEND_API_URL`` points to ``localhost``/``127.0.0.1`` AND we
       are on Streamlit Cloud (there is no external process to rely on).

    In all other cases (a real external URL is provided, or we are running
    locally with a manually-started backend), this function is a no-op and
    returns ``True`` immediately.

    Returns:
        True if the backend is available (already running or successfully
        started), False if it could not be started.
    """
    global _BACKEND_LAUNCH_ATTEMPTED
    if _BACKEND_LAUNCH_ATTEMPTED:
        return True  # Already attempted in this process; trust it succeeded.

    # Lazy import to avoid forcing these imports at module load time.
    from src.config_runtime import get_config_value

    backend_url = str(get_config_value("OKR_BACKEND_API_URL", "")).strip()

    # Detect Streamlit Cloud runtime
    is_cloud = bool(
        os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("IS_STREAMLIT_CLOUD")
    )

    # Decide whether to self-host the backend
    want_auto = backend_url.lower() == "auto"
    want_auto_cloud_empty = is_cloud and not backend_url
    want_auto_cloud_localhost = is_cloud and _is_localhost_url(backend_url)

    if not (want_auto or want_auto_cloud_empty or want_auto_cloud_localhost):
        # External backend configured and we are not on cloud — assume managed.
        return True

    _BACKEND_LAUNCH_ATTEMPTED = True  # Mark as attempted regardless of outcome.

    # ---- Resolve the target host:port the backend should bind to ----
    if want_auto or want_auto_cloud_empty:
        host = str(get_config_value("OKR_BACKEND_HOST", "127.0.0.1")).strip() or "127.0.0.1"
        port_str = str(get_config_value("OKR_BACKEND_PORT", "8100")).strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 8100
    else:
        # Localhost URL detected on Streamlit Cloud — parse host AND port from the URL.
        # The URL-embedded port takes priority over OKR_BACKEND_PORT to avoid mismatches.
        url_host, url_port = _parse_host_port_from_url(backend_url, default_port=8100)
        host = "127.0.0.1" if url_host in ("localhost",) else url_host
        # Allow OKR_BACKEND_PORT env var to override the URL port if explicitly set
        port_override = os.getenv("OKR_BACKEND_PORT", "").strip()
        port = int(port_override) if port_override.isdigit() else url_port

    # If something is already listening on the port, trust it.
    if is_port_open(host, port):
        _LOGGER.info("Embedded backend already reachable on %s:%d.", host, port)
        return True

    # ---- Locate repo root ----
    repo_root = _find_repo_root()
    if repo_root is None:
        _LOGGER.error(
            "Backend launcher could not locate 'backend_app/' directory. "
            "Ensure the repository layout is intact."
        )
        return False

    _LOGGER.info("Launching embedded backend on %s:%d …", host, port)

    # ---- Build environment for the child process ----
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root
    env["OKR_BACKEND_HOST"] = host
    env["OKR_BACKEND_PORT"] = str(port)

    # Propagate service token so the backend can authenticate requests
    token = str(get_config_value("OKR_BACKEND_SERVICE_TOKEN", "")).strip()
    if token:
        env["OKR_BACKEND_SERVICE_TOKEN"] = token

    # On Streamlit Cloud the runtime env should be set explicitly to avoid
    # the backend defaulting to "memory" security state.
    if is_cloud and "OKR_ENV" not in env and "OKR_RUNTIME_ENV" not in env:
        env.setdefault("OKR_ENV", "production")

    cmd = [sys.executable, "-m", "backend_app.run_api"]

    try:
        if os.name == "nt":  # Windows
            subprocess.Popen(
                cmd,
                cwd=repo_root,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                | subprocess.DETACHED_PROCESS,  # type: ignore[attr-defined]
            )
        else:  # Linux / macOS (Streamlit Cloud runs Linux)
            subprocess.Popen(
                cmd,
                cwd=repo_root,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except Exception as exc:
        _LOGGER.error("Failed to spawn embedded backend process: %s", exc)
        return False

    # ---- Poll until the port opens (max 15 s) ----
    max_polls = 30  # 30 × 0.5 s = 15 s
    for i in range(max_polls):
        time.sleep(0.5)
        if is_port_open(host, port):
            _LOGGER.info(
                "Embedded backend is up on %s:%d (after %.1f s).",
                host, port, (i + 1) * 0.5,
            )
            return True

    _LOGGER.warning(
        "Embedded backend was launched but port %d is still closed after 15 s. "
        "The app may experience backend connectivity issues.",
        port,
    )
    return False
