"""cosign_sign_with_retry: bounded retries around `cosign sign`, never a silent pass."""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

from scripts import cosign_sign_with_retry as signer

REF = "ghcr.io/example/okr/web@sha256:" + "a" * 64


class _Script:
    """A fake `run` that returns a scripted exit code per call and records the calls."""

    def __init__(self, *codes: int) -> None:
        self.codes = list(codes)
        self.calls: list[tuple[list[str], float]] = []

    def __call__(self, argv, timeout) -> int:
        self.calls.append((list(argv), timeout))
        return self.codes.pop(0)


def _sign(script, **kwargs):
    sleeps: list[float] = []
    logs: list[str] = []
    code = signer.sign_with_retry(
        REF, run=script, sleep=sleeps.append, log=logs.append, **kwargs
    )
    return code, sleeps, logs


def test_first_attempt_success_does_not_retry_or_sleep():
    script = _Script(0)
    code, sleeps, _ = _sign(script)
    assert code == 0
    assert len(script.calls) == 1
    assert sleeps == []


def test_signs_the_exact_digest_reference_with_yes():
    script = _Script(0)
    _sign(script)
    assert script.calls[0][0] == ["cosign", "sign", "--yes", REF]


def test_transient_failure_is_retried_and_then_succeeds():
    script = _Script(1, 1, 0)
    code, sleeps, logs = _sign(script)
    assert code == 0
    assert len(script.calls) == 3
    assert sleeps == [
        20.0,
        40.0,
    ]  # linear backoff between attempts, none after the last
    assert any("signed on attempt 3 of 3" in line for line in logs)


def test_failure_on_every_attempt_fails_with_the_last_exit_code():
    script = _Script(1, 1, 7)
    code, sleeps, logs = _sign(script)
    assert code == 7
    assert len(script.calls) == 3
    assert len(sleeps) == 2
    assert any("failed on all 3 attempts" in line for line in logs)


def test_attempt_count_and_timeout_are_honoured():
    script = _Script(1, 1)
    code, _, _ = _sign(script, attempts=2, attempt_timeout=9.0)
    assert code == 1
    assert len(script.calls) == 2
    assert {timeout for _, timeout in script.calls} == {9.0}


def test_a_tag_reference_is_refused_without_calling_cosign():
    script = _Script()
    logs: list[str] = []
    code = signer.sign_with_retry(
        "ghcr.io/example/okr/web:latest",
        run=script,
        sleep=lambda _s: None,
        log=logs.append,
    )
    assert code == 2
    assert script.calls == []
    assert logs


def test_zero_attempts_is_a_programming_error():
    with pytest.raises(ValueError):
        signer.sign_with_retry(REF, attempts=0, run=_Script(), sleep=lambda _s: None)


def test_a_timed_out_attempt_reports_124(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="cosign", timeout=1)

    monkeypatch.setattr(signer.subprocess, "run", fake_run)
    assert signer._run_cosign(["cosign", "sign"], 1.0) == 124


def test_run_cosign_returns_the_process_exit_code(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return types.SimpleNamespace(returncode=3)

    monkeypatch.setattr(signer.subprocess, "run", fake_run)
    assert signer._run_cosign(["cosign", "sign", "--yes", REF], 5.0) == 3
    assert seen["argv"][-1] == REF
    assert seen["kwargs"]["timeout"] == 5.0
    assert seen["kwargs"].get("shell") is not True


def test_main_returns_the_signing_exit_code(monkeypatch):
    calls: list[str] = []

    def fake_sign(ref, **_kwargs):
        calls.append(ref)
        return 5

    monkeypatch.setattr(signer, "sign_with_retry", fake_sign)
    assert signer.main([REF]) == 5
    assert calls == [REF]


def test_script_runs_as_a_program_and_refuses_a_tag():
    result = subprocess.run(
        [sys.executable, "scripts/cosign_sign_with_retry.py", "ghcr.io/x/y:tag"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "digest reference" in result.stdout


def _publish_steps() -> list[dict]:
    yaml = pytest.importorskip("yaml")
    path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "publish-ghcr.yml"
    )
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    return [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps") or []
        if isinstance(step, dict)
    ]


def test_publish_workflow_signs_through_the_retry_script_on_the_digest():
    steps = _publish_steps()
    sign = next(s for s in steps if s.get("name") == "Sign published image digest")
    run = sign["run"]
    assert "scripts/cosign_sign_with_retry.py" in run
    assert "${IMAGE_NAME}@${IMAGE_DIGEST}" in run
    assert "cosign sign" not in run, "a bare cosign sign has no retry"


def test_publish_workflow_signing_still_precedes_the_digest_fragment():
    names = [s.get("name") for s in _publish_steps()]
    assert names.index("Sign published image digest") < names.index(
        "Write image digest fragment"
    )
