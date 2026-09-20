from __future__ import annotations

import json

import pytest

from scripts import slo_probe


def test_probe_output_writes_sanitized_machine_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        slo_probe,
        "probe",
        lambda *args, **kwargs: [
            {
                "slo": "healthz",
                "target_s": 2.0,
                "measured_s": 0.1,
                "pass": True,
                "detail": "status=200",
            }
        ],
    )
    output = tmp_path / "evidence.json"

    result = slo_probe.main(
        [
            "--base-url",
            "https://example.test",
            "--username",
            "synthetic-user",
            "--password",
            "super-secret",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["schema_version"] == 1
    assert payload["passed"] == 1
    serialized = output.read_text(encoding="utf-8")
    assert "super-secret" not in serialized
    assert "response_body" not in serialized


def test_probe_accepts_password_from_environment(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_probe(base_url: str, username: str, password: str, **kwargs):
        captured.update(base_url=base_url, username=username, password=password)
        return []

    monkeypatch.setattr(slo_probe, "probe", fake_probe)
    monkeypatch.setenv("PROBE_PASSWORD", "env-secret")

    assert (
        slo_probe.main(
            [
                "--base-url",
                "https://example.test",
                "--username",
                "synthetic-user",
                "--password-env",
                "PROBE_PASSWORD",
            ]
        )
        == 0
    )
    assert captured["password"] == "env-secret"


def test_probe_rejects_empty_password_environment(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_PROBE_PASSWORD", raising=False)

    with pytest.raises(SystemExit):
        slo_probe.main(
            [
                "--base-url",
                "https://example.test",
                "--username",
                "synthetic-user",
                "--password-env",
                "MISSING_PROBE_PASSWORD",
            ]
        )
