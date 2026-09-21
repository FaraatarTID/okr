from __future__ import annotations

import sys

from scripts import verify_deploy_readiness


def test_release_gate_checks_bff_liveness_and_backend_aware_readiness(monkeypatch) -> None:
    checked_urls: list[str] = []

    def fake_http(url: str, timeout_seconds: float) -> tuple[bool, str]:
        del timeout_seconds
        checked_urls.append(url)
        return (not url.endswith("/readyz"), "simulated result")

    monkeypatch.setattr(verify_deploy_readiness, "_http_json", fake_http)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_deploy_readiness.py",
            "--skip-compose",
            "--timeout-seconds",
            "1",
            "--retry-interval",
            "0.25",
        ],
    )

    assert verify_deploy_readiness.main() == 1
    assert "http://127.0.0.1:3001/livez" in checked_urls
    assert "http://127.0.0.1:3001/readyz" in checked_urls
