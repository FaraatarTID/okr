import json
from pathlib import Path
import shutil

import scripts.verify_logging_contract as verifier


ROOT = Path(__file__).resolve().parents[1]


def test_repository_logging_contract_passes() -> None:
    assert verifier.validate_logging_contract(ROOT) == []


def test_contract_rejects_raw_secret_inputs(tmp_path: Path) -> None:
    for relative in verifier.BACKEND_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            'import json\ndef log_payload(*, event, **fields):\n'
            '    return json.dumps({"event": event, "ts": "now", **fields})\n'
            if relative == verifier.BACKEND_FILES[0]
            else 'build_observability_log_payload(request.headers["authorization"])\n'
        )
        path.write_text(content, encoding="utf-8")
    audit = tmp_path / verifier.AUDIT_FILE
    audit.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / verifier.AUDIT_FILE, audit)
    bff = tmp_path / verifier.BFF_FILE
    bff.parent.mkdir(parents=True, exist_ok=True)
    bff.write_text(
        """const app = Fastify({ logger: true });
function buildBffLogPayload(event, request, status) {
  return { event, ts: new Date().toISOString(), authorization: request.headers.authorization };
}
app.log.info(buildBffLogPayload('ok', request, 200));
app.log.error(buildBffLogPayload('error', request, 500));
type BffRequestState = {};
""",
        encoding="utf-8",
    )

    errors = verifier.validate_logging_contract(tmp_path)

    assert any("authorization" in error for error in errors)


def test_contract_rejects_missing_structured_bff_timestamp(tmp_path: Path) -> None:
    for relative in verifier.BACKEND_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            'import json\ndef log_payload(*, event, **fields):\n'
            '    return json.dumps({"event": event, "ts": "now", **fields})\n'
            if relative == verifier.BACKEND_FILES[0]
            else "build_observability_log_payload()\n"
        )
        path.write_text(content, encoding="utf-8")
    audit = tmp_path / verifier.AUDIT_FILE
    audit.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / verifier.AUDIT_FILE, audit)
    bff = tmp_path / verifier.BFF_FILE
    bff.parent.mkdir(parents=True, exist_ok=True)
    bff.write_text(
        """const app = Fastify({ logger: true });
function buildBffLogPayload(event, request, status) {
  return { event };
}
app.log.info(buildBffLogPayload('ok', request, 200));
app.log.error(buildBffLogPayload('error', request, 500));
type BffRequestState = {};
""",
        encoding="utf-8",
    )

    errors = verifier.validate_logging_contract(tmp_path)

    assert "BFF log payload must include ts" in errors


def test_contract_rejects_file_based_audit_sink(tmp_path: Path) -> None:
    for relative in verifier.BACKEND_FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    bff = tmp_path / verifier.BFF_FILE
    bff.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / verifier.BFF_FILE, bff)

    audit = tmp_path / verifier.AUDIT_FILE
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        "import logging\n"
        "logging.FileHandler('audit.log')\n",
        encoding="utf-8",
    )

    errors = verifier.validate_logging_contract(tmp_path)

    assert "src/audit.py must not use FileHandler" in errors


def test_observability_payload_redacts_sensitive_keys() -> None:
    from src.observability_metrics import log_payload

    payload = json.loads(
        log_payload(
            event="test",
            details={"authorization": "Bearer hidden", "safe": "value"},
        )
    )

    assert payload["details"] == {
        "authorization": "[REDACTED]",
        "safe": "value",
    }


def test_contract_requires_centralized_redaction(tmp_path: Path) -> None:
    for relative in verifier.BACKEND_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            'import json\ndef log_payload(*, event, **fields):\n'
            '    return json.dumps({"event": event, "ts": "now", **fields})\n'
            if relative == verifier.BACKEND_FILES[0]
            else "build_observability_log_payload()\n"
        )
        path.write_text(content, encoding="utf-8")
    audit = tmp_path / verifier.AUDIT_FILE
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        "import logging\n"
        "logging.StreamHandler(sys.stdout)\n"
        "logging.StreamHandler(sys.stderr)\n",
        encoding="utf-8",
    )
    bff = tmp_path / verifier.BFF_FILE
    bff.parent.mkdir(parents=True, exist_ok=True)
    bff.write_text(
        "const app = Fastify({ logger: true });\n"
        "function buildBffLogPayload(event) { return { event, ts: 'now' }; }\n"
        "app.log.info('ok'); app.log.error('error');\n"
        "type BffRequestState = {};\n",
        encoding="utf-8",
    )

    errors = verifier.validate_logging_contract(tmp_path)

    assert any("centralized observability redaction" in error for error in errors)
