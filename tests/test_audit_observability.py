import json


class _StubAuditLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)


class _StubErrorLogger:
    def __init__(self):
        self.messages = []

    def error(self, message):
        self.messages.append(message)

    def exception(self, message, exc_info=None):
        self.messages.append(message)


def test_audit_log_includes_observability_fields(monkeypatch):
    import src.audit as audit
    from src.observability import observability_context

    stub_logger = _StubAuditLogger()
    monkeypatch.setattr(audit, "_get_logger", lambda: stub_logger)

    with observability_context(correlation_id="corr-a", request_id="req-a"):
        audit.audit_log(
            action="test_action",
            entity="test_entity",
            actor="alice",
            details={"k": "v"},
        )

    assert len(stub_logger.messages) == 1
    payload = json.loads(stub_logger.messages[0])
    assert payload.get("correlation_id") == "corr-a"
    assert payload.get("request_id") == "req-a"


def test_error_log_includes_observability_context(monkeypatch):
    import src.audit as audit
    from src.observability import observability_context

    stub_logger = _StubErrorLogger()
    monkeypatch.setattr(audit, "_get_error_logger", lambda: stub_logger)

    with observability_context(correlation_id="corr-e", request_id="req-e"):
        audit.error_log("boom")

    assert len(stub_logger.messages) == 1
    message = stub_logger.messages[0]
    assert "corr-e" in message
    assert "req-e" in message
