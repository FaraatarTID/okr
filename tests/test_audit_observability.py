import json

from sqlmodel import select


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


def test_audit_log_persists_event_to_database(monkeypatch, tmp_path):
    import src.audit as audit
    import src.database as database
    from src.models import AuditEvent
    from src.observability import observability_context

    db_path = tmp_path / "audit_events.db"
    db_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("OKR_DATABASE_URL", db_url)
    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)
    database.run_migrations()



    stub_logger = _StubAuditLogger()
    monkeypatch.setattr(audit, "_get_logger", lambda: stub_logger)
    monkeypatch.setattr(audit, "_AUDIT_DB_FAILURE_REPORTED", False, raising=False)

    with observability_context(correlation_id="corr-db", request_id="req-db"):
        audit.audit_log(
            action="create",
            entity="goal",
            actor="alice",
            details={"success": True, "goal_id": 7},
        )

    with database.get_session_context() as session:
        event = session.exec(
            select(AuditEvent).where(
                AuditEvent.action == "create", AuditEvent.entity == "goal"
            )
        ).first()

    assert event is not None
    assert event.actor == "alice"
    assert event.result == "success"
    assert event.correlation_id == "corr-db"
    assert event.request_id == "req-db"
    assert json.loads(event.details_json).get("goal_id") == 7

    database.get_engine().dispose()
    monkeypatch.setattr(database, "_engine", None, raising=False)
