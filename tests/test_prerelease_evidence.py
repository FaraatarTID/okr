import json

import pytest

from scripts.write_prerelease_evidence import (
    EvidenceValidationError,
    PreReleaseEvidence,
    main,
    write_evidence,
)


def valid_payload() -> dict[str, object]:
    return {
        "commit": "a" * 40,
        "namespace": "okr-pre-release",
        "darkube_build_ids": {
            "web": "darkube-web-4812",
            "bff": "darkube-bff-4813",
            "api": "darkube-api-4814",
            "worker": "darkube-worker-4815",
        },
        "database_resource_id": "dbres-7f31a9",
        "migration_head": "20260901_0001",
        "health_result": "passed",
        "smoke_result": "passed",
        "rollback_result": "not_run",
        "operator": "Mina Operations",
        "timestamp": "2026-09-01T12:30:00Z",
    }


def test_valid_payload_is_strictly_modelled() -> None:
    evidence = PreReleaseEvidence.from_dict(valid_payload())

    result = evidence.to_dict()

    assert result["schema_version"] == 1
    assert set(result["darkube_build_ids"]) == {"web", "bff", "api", "worker"}
    assert result["overall_result"] == "not_passed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("namespace", "https://darkube.app/okr-pre-release"),
        ("database_resource_id", "dbres-example"),
        ("migration_head", "<migration-head>"),
        ("operator", "DATABASE_URL=postgresql://user:password@host/db"),
        ("commit", "not-a-commit"),
    ],
)
def test_forbidden_or_invalid_values_are_rejected(field: str, value: str) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(EvidenceValidationError):
        PreReleaseEvidence.from_dict(payload)


def test_build_ids_must_be_exactly_four_opaque_ids() -> None:
    payload = valid_payload()
    payload["darkube_build_ids"] = {"web": "build-1", "bff": "build-2", "api": "build-3"}

    with pytest.raises(EvidenceValidationError, match="exactly web, bff, api, and worker"):
        PreReleaseEvidence.from_dict(payload)


@pytest.mark.parametrize("field", ["health_result", "smoke_result", "rollback_result"])
def test_check_results_are_enumerated(field: str) -> None:
    payload = valid_payload()
    payload[field] = "passed; see https://example.invalid/log"

    with pytest.raises(EvidenceValidationError):
        PreReleaseEvidence.from_dict(payload)


def test_unknown_fields_and_raw_environment_dumps_are_rejected() -> None:
    payload = valid_payload()
    payload["raw_env"] = "APP_SECRET=do-not-publish"

    with pytest.raises(EvidenceValidationError, match="unknown fields"):
        PreReleaseEvidence.from_dict(payload)


def test_writer_emits_only_sanitized_machine_readable_data(tmp_path) -> None:
    evidence = PreReleaseEvidence.from_dict(valid_payload())
    output = tmp_path / "prerelease-evidence.md"

    write_evidence(evidence, output)

    text = output.read_text(encoding="utf-8")
    block = text.split("```json\n", 1)[1].split("\n```", 1)[0]
    written = json.loads(block)
    assert written["commit"] == "a" * 40
    assert "DATABASE_URL" not in text
    assert "https://" not in text
    assert "production approval" in text


def test_cli_writes_valid_input_and_rejects_invalid_input(tmp_path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "evidence.md"
    input_path.write_text(json.dumps(valid_payload()), encoding="utf-8")

    assert main([str(input_path), str(output_path)]) == 0
    assert output_path.exists()

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps({**valid_payload(), "operator": "TOKEN=secret"}), encoding="utf-8")
    assert main([str(invalid_path), str(tmp_path / "should-not-exist.md")]) == 2


def test_all_passing_checks_are_explicitly_derived() -> None:
    payload = valid_payload()
    payload["rollback_result"] = "passed"

    evidence = PreReleaseEvidence.from_dict(payload)

    assert evidence.to_dict()["overall_result"] == "passed"
