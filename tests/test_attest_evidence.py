from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.attest_evidence import main
from scripts.attestation_verification import verify_attestation_signature


SECRET = "attest-evidence-test-secret"


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OKR_SAAS_ATTESTATION_SECRET", SECRET)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_signs_a_record_the_verifier_accepts(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    _write(path, {"schema_version": 1, "rollback": "rollback"})

    code = main(
        [
            "--record",
            str(path),
            "--key-id",
            "rollback-workflow",
            "--evidence-id",
            "rollback-123",
        ]
    )

    assert code == 0
    signed = json.loads(path.read_text(encoding="utf-8"))
    assert signed["attestation"]["key_id"] == "rollback-workflow"
    assert verify_attestation_signature(signed) == "provider-signed"


def test_signature_covers_the_record_so_later_edits_are_detected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "record.json"
    _write(path, {"schema_version": 1, "rollback": "rollback"})
    main(["--record", str(path), "--key-id", "rollback-workflow", "--evidence-id", "r"])
    signed = json.loads(path.read_text(encoding="utf-8"))

    signed["execution"] = {"status": "SUCCESS"}

    with pytest.raises(Exception, match="does not verify"):
        verify_attestation_signature(signed)


def test_replaces_an_attestation_inherited_from_the_source_payload(
    tmp_path: Path,
) -> None:
    """A derived record cannot keep the attestation of the payload it came from."""
    path = tmp_path / "record.json"
    _write(
        path,
        {
            "schema_version": 1,
            "attestation": {
                "provider": "github-actions",
                "evidence_id": "manifest-1",
                "algorithm": "provider-signed",
                "key_id": "publish-ghcr",
                "issued_at": "2026-09-20T09:00:00Z",
                "signed_payload_sha256": "sha256:" + "0" * 64,
                "signature": "hmac-sha256:" + "0" * 64,
            },
            "rollback": "rollback",
        },
    )

    code = main(
        [
            "--record",
            str(path),
            "--key-id",
            "rollback-workflow",
            "--evidence-id",
            "rollback-123",
        ]
    )

    assert code == 0
    signed = json.loads(path.read_text(encoding="utf-8"))
    assert signed["attestation"]["key_id"] == "rollback-workflow"
    assert verify_attestation_signature(signed) == "provider-signed"


def test_refuses_to_sign_without_key_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OKR_SAAS_ATTESTATION_SECRET", raising=False)
    path = tmp_path / "record.json"
    _write(path, {"schema_version": 1, "rollback": "rollback"})

    code = main(
        ["--record", str(path), "--key-id", "rollback-workflow", "--evidence-id", "r"]
    )

    assert code == 1
    assert "attestation" not in json.loads(path.read_text(encoding="utf-8"))
    assert "refusing to write an unsigned record" in capsys.readouterr().err


def test_rejects_a_record_that_is_not_an_object(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    code = main(
        ["--record", str(path), "--key-id", "rollback-workflow", "--evidence-id", "r"]
    )

    assert code == 1


def test_requires_an_evidence_id_when_no_run_id_is_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`evidence_id` ends up in evidence, so it must never be silently empty."""
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    path = tmp_path / "record.json"
    _write(path, {"schema_version": 1, "rollback": "rollback"})

    code = main(["--record", str(path), "--key-id", "rollback-workflow"])

    assert code == 1


def test_falls_back_to_the_github_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_RUN_ID", "987654321")
    path = tmp_path / "record.json"
    _write(path, {"schema_version": 1, "rollback": "rollback"})

    code = main(["--record", str(path), "--key-id", "rollback-workflow"])

    assert code == 0
    signed = json.loads(path.read_text(encoding="utf-8"))
    assert signed["attestation"]["evidence_id"] == "987654321"
