from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_prerelease_smoke import (
    PreReleaseSmokeResult,
    SmokeCheck,
    main,
    verify_prerelease_smoke,
)


class _SmokeHandler(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, bytes, str]] = {}

    def do_GET(self) -> None:  # noqa: N802
        status, body, content_type = self.responses.get(
            self.path, (404, b"not found", "text/plain")
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


@pytest.fixture()
def smoke_server() -> tuple[str, ThreadingHTTPServer]:
    _SmokeHandler.responses = {
        "/": (200, b"<html><title>pre-release</title></html>", "text/html"),
        "/bff/healthz": (200, b'{"status":"ok"}', "application/json"),
        "/api/healthz": (200, b'{"status":"ok"}', "application/json"),
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SmokeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _kwargs(base_url: str) -> dict[str, Any]:
    return {
        "web_url": f"{base_url}/",
        "bff_health_url": f"{base_url}/bff/healthz",
        "api_health_url": f"{base_url}/api/healthz",
        "worker_evidence": "status=running",
        "migration_head": "20260901_prerelease",
    }


def test_typed_models_are_serializable() -> None:
    check = SmokeCheck("api", True, "status=ok", 200)
    result = PreReleaseSmokeResult((check,), 0.1, "2026-09-01T00:00:00+00:00")
    assert result.ok
    assert result.passed
    assert result.to_dict()["checks"][0]["status_code"] == 200


def test_smoke_result_requires_web_bff_api_worker_and_migration_success(smoke_server: tuple[str, ThreadingHTTPServer]) -> None:
    base_url, _server = smoke_server
    result = verify_prerelease_smoke(**_kwargs(base_url), timeout_seconds=2.0)
    assert result.ok
    assert result.independent_ok
    assert {check.name for check in result.checks} == {"web", "bff", "api", "worker", "migration"}
    assert next(check for check in result.checks if check.name == "worker").evidence_type == "MANUAL_ATTESTATION"
    assert next(check for check in result.checks if check.name == "migration").evidence_type == "MANUAL_ATTESTATION"


def test_smoke_failure_does_not_include_response_body(smoke_server: tuple[str, ThreadingHTTPServer]) -> None:
    from tests._test_credentials import test_password

    fixture_password = test_password("prerelease_smoke")
    _SmokeHandler.responses["/bff/healthz"] = (
        503,
        f'{{"status":"down","password":"{test_password("prerelease_smoke")}"}}'.encode(),
        "application/json",
    )
    base_url, _server = smoke_server
    result = verify_prerelease_smoke(**_kwargs(base_url), timeout_seconds=2.0)
    assert not result.ok
    assert "password" not in result.summary.lower()
    assert fixture_password not in json.dumps(result.to_dict())
    assert next(check for check in result.checks if check.name == "bff").detail == "HTTP 503"


def test_missing_worker_and_migration_evidence_fail_independently(smoke_server: tuple[str, ThreadingHTTPServer]) -> None:
    base_url, _server = smoke_server
    result = verify_prerelease_smoke(
        web_url=f"{base_url}/",
        bff_health_url=f"{base_url}/bff/healthz",
        api_health_url=f"{base_url}/api/healthz",
    )
    assert not result.ok
    assert not next(check for check in result.checks if check.name == "worker").ok
    assert not next(check for check in result.checks if check.name == "migration").ok


def test_health_endpoint_requires_json_status_ok(smoke_server: tuple[str, ThreadingHTTPServer]) -> None:
    _SmokeHandler.responses["/api/healthz"] = (200, b"healthy", "text/plain")
    base_url, _server = smoke_server
    result = verify_prerelease_smoke(**_kwargs(base_url))
    api_check = next(check for check in result.checks if check.name == "api")
    assert not api_check.ok
    assert api_check.detail == "health endpoint returned invalid JSON"


def test_timeout_must_be_finite_and_bounded() -> None:
    with pytest.raises(ValueError, match="finite positive"):
        verify_prerelease_smoke(**_kwargs("http://127.0.0.1:1"), timeout_seconds=float("inf"))
    with pytest.raises(ValueError, match="must not exceed"):
        verify_prerelease_smoke(**_kwargs("http://127.0.0.1:1"), timeout_seconds=61)


def test_cli_json_output_and_failure_exit_code(smoke_server: tuple[str, ThreadingHTTPServer], capsys: pytest.CaptureFixture[str]) -> None:
    base_url, _server = smoke_server
    exit_code = main(
        [
            "--web-url",
            f"{base_url}/",
            "--bff-health-url",
            f"{base_url}/bff/healthz",
            "--api-health-url",
            f"{base_url}/api/healthz",
            "--worker-evidence",
            "status=running",
            "--migration-head",
            "head-1",
            "--expected-migration-head",
            "head-2",
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["checks"][-1]["name"] == "migration"


def test_cli_text_output_can_read_worker_evidence_file(
    smoke_server: tuple[str, ThreadingHTTPServer], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base_url, _server = smoke_server
    evidence_file = tmp_path / "worker-status.txt"
    evidence_file.write_text("status=running\n", encoding="utf-8")
    exit_code = main(
        [
            "--web-url",
            f"{base_url}/",
            "--bff-health-url",
            f"{base_url}/bff/healthz",
            "--api-health-url",
            f"{base_url}/api/healthz",
            "--worker-evidence-file",
            str(evidence_file),
            "--migration-head",
            "head-1",
            "--format",
            "text",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[MANUAL_ATTESTATION] worker" in output
    assert "status=running" not in output
    assert "MANUAL_ATTESTATION" in output
