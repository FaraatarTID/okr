"""Opt-in black-box check for the client-IP overwrite in the Nginx template.

Run with ``OKR_RUN_NGINX_CLIENT_IP_TEST=1 pytest -q
tests/test_nginx_client_ip_overwrite.py``. The test uses only locally cached
container images and never pulls them. It does not establish deployed
reachability or prove that a deployed target uses this template.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUN_ENV = "OKR_RUN_NGINX_CLIENT_IP_TEST"
NGINX_IMAGE_ENV = "OKR_TEST_NGINX_IMAGE"
DEFAULT_NGINX_IMAGE = (
    "nginx@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de"
)
CAPTURE_IMAGE = (
    "python@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b"
)
SPOOFED_CLIENT_IP = "203.0.113.250"


def _docker(*args: str, timeout: float = 20) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("docker")
    if executable is None:
        raise RuntimeError("Docker CLI is unavailable")
    try:
        return subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Docker command failed: {exc}") from exc


def _require_local_image(image: str) -> None:
    try:
        result = _docker("image", "inspect", image)
    except RuntimeError as exc:
        pytest.skip(f"Docker is unavailable for the opt-in Nginx check: {exc}")
    if result.returncode != 0:
        pytest.skip(
            f"Docker image {image!r} is not available locally; this opt-in test never pulls images"
        )


def _nginx_test_config() -> str:
    """Use the tracked Nginx config, changing only the local capture upstream."""
    source = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")
    proxy_pass = re.compile(
        r"(?m)^(?P<indent>[ \t]*)proxy_pass http://127\.0\.0\.1:3000/;(?P<tail>.*)$"
    )
    redirected, replacements = proxy_pass.subn(
        r"\g<indent>proxy_pass http://capture:3000/;\g<tail>", source
    )
    if replacements != 1:
        pytest.fail(
            "expected exactly one active localhost SPA upstream in deploy/nginx.conf; "
            f"found {replacements}"
        )
    return redirected


def _response_json(capture_container: str) -> dict[str, str]:
    request_code = (
        "import json, urllib.request\n"
        "request = urllib.request.Request(\n"
        "    'http://edge/',\n"
        "    headers={\n"
        f"        'Host': 'okr.example.com', 'X-OKR-Client-IP': '{SPOOFED_CLIENT_IP}',\n"
        "        'X-Forwarded-For': '198.51.100.77', 'X-Real-IP': '192.0.2.88',\n"
        "    },\n"
        ")\n"
        "with urllib.request.urlopen(request, timeout=3) as response:\n"
        "    print(response.read().decode('utf-8'))\n"
    )
    result = _docker("exec", capture_container, "python", "-c", request_code, timeout=8)
    if result.returncode != 0:
        raise RuntimeError(f"capture-side request failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _capture_server_code() -> str:
    # This minimal upstream returns the headers Nginx actually sent to it.
    return (
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
        "import json\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        payload = {name: self.headers.get(name, '') for name in "
        "('X-OKR-Client-IP', 'X-Real-IP', 'X-Forwarded-For')}\n"
        "        data = json.dumps(payload).encode()\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-Type', 'application/json')\n"
        "        self.send_header('Content-Length', str(len(data)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(data)\n"
        "    def log_message(self, *args): pass\n"
        "ThreadingHTTPServer(('0.0.0.0', 3000), Handler).serve_forever()\n"
    )


def _wait_for_capture(capture_container: str) -> dict[str, str]:
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _response_json(capture_container)
        except (
            OSError,
            RuntimeError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            time.sleep(0.25)
    raise AssertionError(f"Nginx/capture request did not become ready: {last_error}")


def _cleanup_container(name: str) -> None:
    result = _docker("rm", "--force", name)
    if result.returncode != 0 and "No such container" not in result.stderr:
        raise RuntimeError(
            f"could not remove task-owned container {name}: {result.stderr.strip()}"
        )


def _cleanup_network(name: str) -> None:
    result = _docker("network", "rm", name)
    if result.returncode != 0 and "not found" not in result.stderr.lower():
        raise RuntimeError(
            f"could not remove task-owned network {name}: {result.stderr.strip()}"
        )


@pytest.mark.integration
def test_nginx_overwrites_spoofed_private_client_ip() -> None:
    if os.getenv(RUN_ENV) != "1":
        pytest.skip(f"set {RUN_ENV}=1 to run the local Docker/Nginx integration check")

    try:
        daemon = _docker("version", "--format", "{{.Server.Version}}")
    except RuntimeError as exc:
        pytest.skip(f"Docker daemon is unavailable: {exc}")
    if daemon.returncode != 0:
        pytest.skip(f"Docker daemon is unavailable: {daemon.stderr.strip()}")

    nginx_image = os.getenv(NGINX_IMAGE_ENV, DEFAULT_NGINX_IMAGE)
    _require_local_image(nginx_image)
    _require_local_image(CAPTURE_IMAGE)

    run_id = uuid.uuid4().hex[:12]
    network = f"okr-t31-{run_id}"
    capture = f"okr-t31-capture-{run_id}"
    edge = f"okr-t31-nginx-{run_id}"
    network_created = False
    containers_created: list[str] = []

    try:
        # Keep both containers on an internal network with no host-published
        # ports. The capture container sends the forged-header request to Nginx.
        created = _docker("network", "create", "--internal", network)
        if created.returncode != 0:
            pytest.fail(
                f"could not create isolated Docker network: {created.stderr.strip()}"
            )
        network_created = True

        capture_started = _docker(
            "run",
            "--detach",
            "--pull=never",
            "--name",
            capture,
            "--network",
            network,
            "--network-alias",
            "capture",
            "--entrypoint",
            "python",
            CAPTURE_IMAGE,
            "-u",
            "-c",
            _capture_server_code(),
        )
        if capture_started.returncode != 0:
            pytest.fail(
                f"could not start task-owned capture upstream: {capture_started.stderr.strip()}"
            )
        containers_created.append(capture)

        with TemporaryDirectory(prefix="okr-t31-nginx-") as temp_dir:
            config_path = Path(temp_dir) / "default.conf"
            config_path.write_text(_nginx_test_config(), encoding="utf-8")
            nginx_started = _docker(
                "run",
                "--detach",
                "--pull=never",
                "--name",
                edge,
                "--network",
                network,
                "--network-alias",
                "edge",
                "--volume",
                f"{config_path}:/etc/nginx/conf.d/default.conf:ro",
                nginx_image,
            )
            if nginx_started.returncode != 0:
                pytest.fail(
                    f"could not start task-owned Nginx edge: {nginx_started.stderr.strip()}"
                )
            containers_created.append(edge)

            received = _wait_for_capture(capture)

        private_address = received.get("X-OKR-Client-IP", "")
        real_address = received.get("X-Real-IP", "")
        assert private_address, "the capture upstream received no X-OKR-Client-IP"
        assert private_address != SPOOFED_CLIENT_IP, (
            "Nginx forwarded the caller's forged X-OKR-Client-IP instead of overwriting it"
        )
        assert private_address == real_address, (
            "the private client-IP header did not match Nginx's $remote_addr value"
        )
        assert received.get("X-Forwarded-For", "").startswith("198.51.100.77"), (
            "the request did not carry its deliberately conflicting X-Forwarded-For control"
        )
    finally:
        cleanup_errors: list[str] = []
        for container_name in reversed(containers_created):
            try:
                _cleanup_container(container_name)
            except RuntimeError as exc:
                cleanup_errors.append(str(exc))
        if network_created:
            try:
                _cleanup_network(network)
            except RuntimeError as exc:
                cleanup_errors.append(str(exc))
        if cleanup_errors:
            pytest.fail(
                "task-owned Docker cleanup failed: " + "; ".join(cleanup_errors)
            )
