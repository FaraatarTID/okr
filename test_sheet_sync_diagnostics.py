from pathlib import Path
import sys
from contextlib import contextmanager

from sqlmodel import SQLModel, Session, select


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _bind_temp_db(monkeypatch, sheet_sync, tmp_path):
    import src.database as database

    db_path = tmp_path / "sheet_sync_diag.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr(sheet_sync, "get_engine", lambda: engine, raising=True)

    @contextmanager
    def _session_ctx():
        session = Session(engine, expire_on_commit=False)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(sheet_sync, "get_session_context", _session_ctx, raising=True)
    return engine


def test_sheet_sync_diagnostics_capture_structured_errors(monkeypatch):
    import src.services.sheet_sync as sheet_sync

    monkeypatch.setattr(sheet_sync.st, "secrets", {}, raising=False)
    monkeypatch.setattr(sheet_sync, "audit_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync, "error_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_connect", lambda self: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_retry_storage_available", lambda self: False, raising=True)

    service = sheet_sync.SheetSyncService()
    assert service.is_ready() is False

    service._set_error("Connection failed", code="SYNC_CONNECT_FAILED")
    service._set_error("Push failed", code="SYNC_PUSH_FAILED", context={"sheet": "Goals"})

    diag = service.get_diagnostics()
    assert diag["ready"] is False
    assert diag["last_error"] == "Push failed"
    assert diag["last_error_code"] == "SYNC_PUSH_FAILED"
    assert diag["error_count"] == 2
    assert len(diag["recent_errors"]) == 2
    assert diag["recent_errors"][-1]["context"] == {"sheet": "Goals"}


class _DummyNode:
    __tablename__ = "Goals"

    def __init__(self, node_id: int, title: str):
        self.id = node_id
        self.title = title

    def model_dump(self):
        return {"id": self.id, "title": self.title}


class _FakeWorksheet:
    def __init__(self):
        self._headers = []
        self._rows = []

    def row_values(self, row_idx: int):
        if row_idx == 1:
            return list(self._headers)
        return []

    def append_row(self, values):
        if not self._headers:
            self._headers = list(values)
            return
        self._rows.append(list(values))

    def col_values(self, col_idx: int):
        if col_idx != 1:
            return []
        if not self._headers:
            return []
        col = [self._headers[0]]
        for row in self._rows:
            col.append(str(row[0]) if row else "")
        return col

    def update(self, range_name: str, values):
        row_num = int(range_name.lstrip("A"))
        row_idx = row_num - 2
        while row_idx >= len(self._rows):
            self._rows.append(["" for _ in self._headers])
        self._rows[row_idx] = list(values[0])

    def delete_rows(self, row_num: int):
        if row_num <= 1:
            self._headers = []
            self._rows = []
            return
        row_idx = row_num - 2
        if 0 <= row_idx < len(self._rows):
            self._rows.pop(row_idx)


class _FakeSpreadsheet:
    def __init__(self):
        self._worksheets = {}

    def worksheet(self, name: str):
        if name not in self._worksheets:
            self._worksheets[name] = _FakeWorksheet()
        return self._worksheets[name]


def test_sheet_sync_retry_queue_is_bounded_and_deduplicates(monkeypatch):
    import src.services.sheet_sync as sheet_sync

    monkeypatch.setattr(sheet_sync.st, "secrets", {}, raising=False)
    monkeypatch.setattr(sheet_sync, "audit_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync, "error_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_connect", lambda self: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_retry_storage_available", lambda self: False, raising=True)

    service = sheet_sync.SheetSyncService()
    service.retry_queue_limit = 2

    # Offline queueing
    service.push_update(_DummyNode(1, "A"))
    service.push_update(_DummyNode(1, "A2"))  # same key should replace
    service.push_update(_DummyNode(2, "B"))
    service.push_update(_DummyNode(3, "C"))   # pushes queue over limit

    diag = service.get_diagnostics()
    assert diag["retry_queue_size"] == 2
    assert diag["retry_dropped_count"] == 1
    payload_titles = [item["payload"]["data"]["title"] for item in service.retry_queue]
    assert "A2" not in payload_titles  # oldest dropped due to queue bound
    assert "B" in payload_titles
    assert "C" in payload_titles


def test_sheet_sync_retry_queue_flushes_when_service_becomes_ready(monkeypatch):
    import src.services.sheet_sync as sheet_sync

    monkeypatch.setattr(sheet_sync.st, "secrets", {}, raising=False)
    monkeypatch.setattr(sheet_sync, "audit_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync, "error_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_connect", lambda self: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_retry_storage_available", lambda self: False, raising=True)

    service = sheet_sync.SheetSyncService()

    service.push_update(_DummyNode(1, "A"))
    service.push_update(_DummyNode(2, "B"))
    assert service.get_diagnostics()["retry_queue_size"] == 2

    service.client = object()
    fake_book = _FakeSpreadsheet()
    service.spreadsheet = fake_book

    result = service.process_retry_queue(force=True, max_items=10)
    assert result["processed"] == 2
    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert service.get_diagnostics()["retry_queue_size"] == 0
    assert service.get_diagnostics()["retry_sent_count"] == 2

    goals_ws = fake_book.worksheet("Goals")
    # header + 2 rows
    assert goals_ws.col_values(1) == ["id", "1", "2"]


def test_sheet_sync_retry_queue_persists_across_instances(monkeypatch, tmp_path):
    import src.services.sheet_sync as sheet_sync
    from src.models import SyncRetryEvent

    monkeypatch.setattr(sheet_sync.st, "secrets", {}, raising=False)
    monkeypatch.setattr(sheet_sync, "audit_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync, "error_log", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sheet_sync.SheetSyncService, "_connect", lambda self: None, raising=True)

    engine = _bind_temp_db(monkeypatch, sheet_sync, tmp_path)

    service1 = sheet_sync.SheetSyncService()
    service1.push_update(_DummyNode(1, "Persisted"))

    with Session(engine, expire_on_commit=False) as session:
        persisted_rows = session.exec(select(SyncRetryEvent)).all()
        assert len(persisted_rows) == 1
        assert persisted_rows[0].queue_key == "Goals::1"

    service2 = sheet_sync.SheetSyncService()
    assert service2.get_diagnostics()["retry_queue_size"] == 1

    service2.client = object()
    service2.spreadsheet = _FakeSpreadsheet()
    result = service2.process_retry_queue(force=True, max_items=10)
    assert result["succeeded"] == 1

    with Session(engine, expire_on_commit=False) as session:
        remaining_rows = session.exec(select(SyncRetryEvent)).all()
        assert len(remaining_rows) == 0

    engine.dispose()
