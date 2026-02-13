import streamlit as st
from sqlmodel import Session, select, SQLModel
from sqlalchemy import inspect as sa_inspect, text
import pandas as pd
from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, Optional

# Models to sync
from src.models import (
    User, Cycle, Goal, Objective, KeyResult, Task, 
    WorkLog, CheckIn, Retrospective, SyncRetryEvent
)
from src.database import get_engine, get_session_context
from src.config import is_production
from src.audit import audit_log, error_log
from src.utils.time_utils import utc_now

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class SheetSyncService:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.id_cache = {} # Cache for ID -> Row Number per sheet
        self.last_error = None
        self.last_error_code = None
        self.last_error_at = None
        self.error_count = 0
        self.error_history = []
        self.retry_queue = []
        self.retry_queue_limit = int(st.secrets.get("SYNC_RETRY_QUEUE_LIMIT", 200))
        self.retry_base_seconds = 2
        self.retry_max_seconds = 300
        self.retry_max_attempts = 8
        self.retry_sent_count = 0
        self.retry_failed_count = 0
        self.retry_dropped_count = 0
        self.retry_exhausted_count = 0
        self.last_retry_flush_at = None
        self._retry_storage_known = None
        self._retry_storage_checked_at = 0.0
        self.spreadsheet_name = st.secrets.get("GCP_SPREADSHEET_NAME", "OKR_DB")
        self._connect()
        self._load_retry_queue_from_db()
        if self.is_ready() and self.retry_queue:
            self.process_retry_queue(force=False, max_items=25)

    def _clear_last_error(self):
        self.last_error = None
        self.last_error_code = None
        self.last_error_at = None

    def _set_error(
        self,
        message: str,
        exc: Optional[Exception] = None,
        code: str = "SYNC_ERROR",
        context: Optional[Dict[str, Any]] = None,
    ):
        """Record and surface sync errors for diagnostics."""
        if exc:
            message = f"{message}: {exc}"
        ts = utc_now().isoformat()
        self.last_error = message
        self.last_error_code = code
        self.last_error_at = ts
        self.error_count += 1
        event = {
            "ts": ts,
            "code": code,
            "message": message,
            "context": context or {},
        }
        self.error_history.append(event)
        if len(self.error_history) > 25:
            self.error_history = self.error_history[-25:]
        error_log(f"[SheetSync:{code}] {message}", exc=exc)
        audit_log("sync_error", "sheet_sync", details=event)
        print(f"[SheetSync] {message}")

    def _connect(self):
        """Connect to Google Sheets API."""
        self._clear_last_error()
        if is_production():
            self._set_error(
                "Google Sheets sync is disabled in production mode.",
                code="SYNC_DISABLED_PRODUCTION",
            )
            return
        if "gcp_service_account" not in st.secrets:
            self._set_error(
                "Missing gcp_service_account in secrets",
                code="SYNC_MISSING_CREDENTIALS",
            )
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials
            service_account_info = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            self.client = gspread.authorize(creds)
            
            try:
                self.spreadsheet = self.client.open(self.spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                self._set_error(
                    f"Spreadsheet '{self.spreadsheet_name}' not found",
                    code="SYNC_SPREADSHEET_NOT_FOUND",
                )
            except Exception as e:
                self._set_error(
                    f"Failed to open '{self.spreadsheet_name}'",
                    exc=e,
                    code="SYNC_OPEN_FAILED",
                )
        except Exception as e:
            self._set_error("Connection Failed", exc=e, code="SYNC_CONNECT_FAILED")

    def is_ready(self):
        """Check if the sync service is connected and ready."""
        return self.client is not None and self.spreadsheet is not None

    def get_last_error(self):
        """Return the last connection or sync error."""
        return self.last_error

    def get_diagnostics(self) -> Dict[str, Any]:
        """Structured sync diagnostics for UI and debugging."""
        return {
            "ready": self.is_ready(),
            "last_error": self.last_error,
            "last_error_code": self.last_error_code,
            "last_error_at": self.last_error_at,
            "error_count": self.error_count,
            "recent_errors": list(self.error_history[-5:]),
            "retry_queue_size": len(self.retry_queue),
            "retry_queue_limit": self.retry_queue_limit,
            "retry_sent_count": self.retry_sent_count,
            "retry_failed_count": self.retry_failed_count,
            "retry_dropped_count": self.retry_dropped_count,
            "retry_exhausted_count": self.retry_exhausted_count,
            "last_retry_flush_at": self.last_retry_flush_at,
            "retry_persistence_enabled": self._retry_storage_available(),
        }

    def _retry_storage_available(self) -> bool:
        now_ts = time.time()
        if self._retry_storage_known is not None and (now_ts - self._retry_storage_checked_at) < 5:
            return bool(self._retry_storage_known)
        try:
            inspector = sa_inspect(get_engine())
            available = "sync_retry_event" in set(inspector.get_table_names())
        except Exception:
            available = False
        self._retry_storage_known = available
        self._retry_storage_checked_at = now_ts
        return available

    @staticmethod
    def _epoch_to_naive_utc(value: float) -> datetime:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _naive_utc_to_epoch(value: Optional[datetime]) -> float:
        if value is None:
            return time.time()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).timestamp()
        return value.astimezone(timezone.utc).timestamp()

    def _persist_retry_item_db(self, item: Dict[str, Any]) -> None:
        if not self._retry_storage_available():
            return
        try:
            with get_session_context() as session:
                row = session.exec(
                    select(SyncRetryEvent).where(SyncRetryEvent.queue_key == item["key"])
                ).first()
                payload_json = json.dumps(item["payload"], ensure_ascii=False)
                next_attempt_at = self._epoch_to_naive_utc(item.get("next_attempt_at", time.time()))
                if row:
                    row.payload_json = payload_json
                    row.attempts = int(item.get("attempts", 0))
                    row.next_attempt_at = next_attempt_at
                    row.last_error_code = item.get("last_error_code")
                    row.last_error = item.get("last_error")
                    row.updated_at = utc_now().replace(tzinfo=None)
                    session.add(row)
                else:
                    session.add(
                        SyncRetryEvent(
                            queue_key=item["key"],
                            payload_json=payload_json,
                            attempts=int(item.get("attempts", 0)),
                            next_attempt_at=next_attempt_at,
                            last_error_code=item.get("last_error_code"),
                            last_error=item.get("last_error"),
                        )
                    )
        except Exception as exc:
            self._set_error(
                "Failed to persist retry queue item",
                exc=exc,
                code="SYNC_RETRY_PERSIST_FAILED",
                context={"key": item.get("key")},
            )

    def _delete_retry_item_db(self, key: str) -> None:
        if not self._retry_storage_available():
            return
        try:
            with get_session_context() as session:
                row = session.exec(
                    select(SyncRetryEvent).where(SyncRetryEvent.queue_key == key)
                ).first()
                if row:
                    session.delete(row)
        except Exception as exc:
            self._set_error(
                "Failed to remove retry queue item from persistence",
                exc=exc,
                code="SYNC_RETRY_DELETE_FAILED",
                context={"key": key},
            )

    def _load_retry_queue_from_db(self) -> None:
        if not self._retry_storage_available():
            return
        try:
            loaded_queue = []
            with get_session_context() as session:
                rows = session.exec(
                    select(SyncRetryEvent)
                    .order_by(SyncRetryEvent.next_attempt_at)
                    .limit(self.retry_queue_limit)
                ).all()
                for row in rows:
                    try:
                        payload = json.loads(row.payload_json)
                    except Exception:
                        session.delete(row)
                        continue
                    loaded_queue.append(
                        {
                            "key": row.queue_key,
                            "payload": payload,
                            "attempts": int(row.attempts or 0),
                            "queued_at": row.created_at.isoformat() if row.created_at else utc_now().isoformat(),
                            "next_attempt_at": self._naive_utc_to_epoch(row.next_attempt_at),
                            "last_error_code": row.last_error_code,
                            "last_error": row.last_error,
                        }
                    )
            if loaded_queue:
                deduped = {}
                for item in loaded_queue:
                    deduped[item["key"]] = item
                self.retry_queue = list(deduped.values())
        except Exception as exc:
            self._set_error("Failed to load retry queue from persistence", exc=exc, code="SYNC_RETRY_LOAD_FAILED")

    def reconnect(self):
        """Manually trigger a reconnection attempt."""
        self._connect()
        if self.is_ready():
            self.process_retry_queue(force=True, max_items=100)
        return self.is_ready()

    def _resolve_sheet_name(self, model_obj) -> Optional[str]:
        sheet_name = getattr(model_obj, "__tablename__", None)
        if sheet_name:
            return sheet_name
        if isinstance(model_obj, User): return "Users"
        if isinstance(model_obj, Cycle): return "Cycles"
        if isinstance(model_obj, Goal): return "Goals"
        if isinstance(model_obj, Objective): return "Objectives"
        if isinstance(model_obj, KeyResult): return "KeyResults"
        if isinstance(model_obj, Task): return "Tasks"
        if isinstance(model_obj, CheckIn): return "CheckIns"
        if isinstance(model_obj, WorkLog): return "WorkLogs"
        if isinstance(model_obj, Retrospective): return "Retrospectives"
        return None

    def _build_payload(self, model_obj, delete: bool) -> Optional[Dict[str, Any]]:
        sheet_name = self._resolve_sheet_name(model_obj)
        if not sheet_name:
            return None
        data = model_obj.model_dump()
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return {
            "sheet_name": sheet_name,
            "obj_id": str(data.get("id")),
            "delete": bool(delete),
            "data": data,
        }

    def _payload_key(self, payload: Dict[str, Any]) -> str:
        return f"{payload.get('sheet_name')}::{payload.get('obj_id')}"

    def _enqueue_retry(self, payload: Dict[str, Any], code: str, exc: Optional[Exception] = None) -> None:
        now_ts = time.time()
        key = self._payload_key(payload)
        for item in self.retry_queue:
            if item.get("key") == key:
                item["payload"] = payload
                item["last_error_code"] = code
                item["last_error"] = str(exc) if exc else None
                item["next_attempt_at"] = now_ts
                self._persist_retry_item_db(item)
                return

        if len(self.retry_queue) >= self.retry_queue_limit:
            dropped = self.retry_queue.pop(0)
            self._delete_retry_item_db(dropped.get("key", ""))
            self.retry_dropped_count += 1
            self._set_error(
                "Retry queue full. Oldest pending sync operation dropped.",
                code="SYNC_RETRY_QUEUE_DROPPED",
                context={"queue_limit": self.retry_queue_limit},
            )

        self.retry_queue.append(
            {
                "key": key,
                "payload": payload,
                "attempts": 0,
                "queued_at": utc_now().isoformat(),
                "next_attempt_at": now_ts,
                "last_error_code": code,
                "last_error": str(exc) if exc else None,
            }
        )
        self._persist_retry_item_db(self.retry_queue[-1])

    def _backoff_seconds(self, attempts: int) -> int:
        exp = max(0, attempts - 1)
        return min(self.retry_max_seconds, self.retry_base_seconds * (2 ** exp))

    def _push_payload(self, payload: Dict[str, Any]) -> None:
        if not self.is_ready():
            raise RuntimeError("Sync service is not ready")

        sheet_name = payload["sheet_name"]
        worksheet = self.spreadsheet.worksheet(sheet_name)
        data = payload["data"]
        obj_id = payload["obj_id"]

        headers = worksheet.row_values(1)
        if not headers:
            headers = list(data.keys())
            worksheet.append_row(headers)

        row_values = [data.get(h, "") for h in headers]
        if sheet_name not in self.id_cache:
            self.id_cache[sheet_name] = self._get_id_map(worksheet)

        row_num = self.id_cache[sheet_name].get(obj_id)

        if payload.get("delete"):
            if row_num:
                worksheet.delete_rows(row_num)
                if sheet_name in self.id_cache:
                    del self.id_cache[sheet_name]
        else:
            if row_num:
                worksheet.update(range_name=f"A{row_num}", values=[row_values])
            else:
                worksheet.append_row(row_values)
                if sheet_name in self.id_cache:
                    del self.id_cache[sheet_name]

    def process_retry_queue(self, force: bool = False, max_items: int = 25) -> Dict[str, int]:
        """Attempt queued sync operations with bounded retries and exponential backoff."""
        if not self.is_ready() or not self.retry_queue:
            return {"processed": 0, "succeeded": 0, "failed": 0}

        now_ts = time.time()
        processed = 0
        succeeded = 0
        failed = 0

        for item in list(self.retry_queue):
            if processed >= max_items:
                break
            if not force and item.get("next_attempt_at", 0) > now_ts:
                continue

            processed += 1
            payload = item["payload"]
            try:
                self._push_payload(payload)
                self.retry_queue.remove(item)
                self._delete_retry_item_db(item.get("key", ""))
                self.retry_sent_count += 1
                succeeded += 1
            except Exception as exc:
                item["attempts"] += 1
                item["last_error_code"] = "SYNC_RETRY_FAILED"
                item["last_error"] = str(exc)
                item["next_attempt_at"] = now_ts + self._backoff_seconds(item["attempts"])
                self.retry_failed_count += 1
                failed += 1
                if item["attempts"] >= self.retry_max_attempts:
                    self.retry_queue.remove(item)
                    self._delete_retry_item_db(item.get("key", ""))
                    self.retry_exhausted_count += 1
                    self._set_error(
                        "Retry attempts exhausted for queued sync operation.",
                        code="SYNC_RETRY_EXHAUSTED",
                        context={"sheet_name": payload.get("sheet_name"), "obj_id": payload.get("obj_id")},
                    )
                else:
                    self._persist_retry_item_db(item)

        self.last_retry_flush_at = utc_now().isoformat()
        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    @staticmethod
    def _normalize_id(value):
        """Normalize IDs from Sheets/local DB to a stable comparable type."""
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else str(value)
        text_value = str(value).strip()
        if not text_value:
            return None
        if text_value.lstrip("-").isdigit():
            try:
                return int(text_value)
            except Exception:
                return text_value
        return text_value

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        # Allow ISO-8601 UTC suffix used by APIs/sheets.
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return None

    @staticmethod
    def _to_naive_utc(value):
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def ensure_schema(self):
        """Ensure all required worksheets exist."""
        if not self.is_ready(): return

        required_sheets = [
            "Users", "Cycles", 
            "Goals", "Objectives", "KeyResults", "Tasks",
            "CheckIns", "WorkLogs", "Retrospectives"
        ]
        
        try:
            existing_titles = [ws.title for ws in self.spreadsheet.worksheets()]
            
            for name in required_sheets:
                if name not in existing_titles:
                    try:
                        self.spreadsheet.add_worksheet(title=name, rows=100, cols=20)
                    except Exception as e:
                        self._set_error(f"Failed to add worksheet '{name}'", e)
        except Exception as e:
            self._set_error("Failed to list worksheets", e)

    def restore_to_local_db(self):
        """Pull all data from Sheets and insert into local SQLite."""
        if not self.is_ready(): return
        self.ensure_schema()
        
        try:
            # 1. Base Tables
            self._restore_table(User, "Users")
            self._restore_table(Cycle, "Cycles")
            # 2. Hierarchy
            self._restore_table(Goal, "Goals")
            self._restore_table(Objective, "Objectives")
            self._restore_table(KeyResult, "KeyResults")
            self._restore_table(Task, "Tasks")
            # 3. Linked Tables
            self._restore_table(CheckIn, "CheckIns")
            self._restore_table(WorkLog, "WorkLogs")
            self._restore_table(Retrospective, "Retrospectives")
        except Exception as e:
            self._set_error("Restore to local DB failed", e)

    def _restore_table(self, model_cls: SQLModel, sheet_name: str):
        """Generic helper to restore a single table."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            if not data: return

            with get_session_context() as session:
                existing_map = {}
                try:
                    rows = session.exec(select(model_cls)).all()
                    for r in rows:
                        ts = getattr(r, "updated_at", getattr(r, "created_at", None))
                        row_id = self._normalize_id(getattr(r, "id", None))
                        if row_id is not None:
                            existing_map[row_id] = ts
                except Exception as e:
                    self._set_error(f"Failed to read local rows for '{sheet_name}'", e)

                for row in data:
                    clean_row = {k: v for k, v in row.items() if v != ''}
                    
                    # Parse sheet timestamp
                    sheet_ts = None
                    if "updated_at" in clean_row and clean_row["updated_at"]:
                        sheet_ts = self._parse_datetime(clean_row["updated_at"])
                    
                    # Convert dates
                    for field in [
                        "created_at",
                        "updated_at",
                        "start_date",
                        "end_date",
                        "deadline",
                        "password_changed_at",
                    ]:
                        if field in clean_row and clean_row[field]:
                            parsed = self._parse_datetime(clean_row[field])
                            if parsed:
                                clean_row[field] = parsed

                    # Check existence
                    obj_id = self._normalize_id(clean_row.get("id"))
                    clean_row["id"] = obj_id
                    if obj_id is None:
                        continue

                    if obj_id in existing_map:
                        local_ts = existing_map[obj_id]
                        should_update = False
                        if sheet_ts and local_ts:
                            sheet_cmp = self._to_naive_utc(sheet_ts)
                            local_cmp = self._to_naive_utc(local_ts)
                            if isinstance(sheet_cmp, datetime) and isinstance(local_cmp, datetime):
                                should_update = sheet_cmp > local_cmp
                            else:
                                should_update = True
                        elif sheet_ts and not local_ts:
                            should_update = True
                        if should_update:
                            local_obj = session.get(model_cls, obj_id)
                            for k, v in clean_row.items():
                                if local_obj is not None and hasattr(local_obj, k):
                                    setattr(local_obj, k, v)
                            if local_obj is not None:
                                session.add(local_obj)
                    else:
                        try:
                            obj = model_cls.model_validate(clean_row)
                            session.add(obj)
                        except Exception as e:
                            self._set_error(f"Failed to insert row in '{sheet_name}'", e)
                session.commit()
        except Exception as e:
            self._set_error(f"Restore failed for table '{sheet_name}'", e)

    def _get_id_map(self, worksheet):
        """Get a map of ID -> Row Number from the sheet."""
        try:
            ids = worksheet.col_values(1)
            return {str(val): i + 1 for i, val in enumerate(ids) if val}
        except Exception as e:
            self._set_error("Failed to read ID map from worksheet", e)
            return {}

    def push_update(self, model_obj, delete=False):
        """Push a single object change to the Sheet."""
        payload = self._build_payload(model_obj, delete)
        if payload is None:
            return

        if not self.is_ready():
            self._enqueue_retry(payload, code="SYNC_UNAVAILABLE")
            return

        if self.retry_queue:
            self.process_retry_queue(force=False, max_items=5)

        try:
            self._push_payload(payload)
        except Exception as e:
            self._enqueue_retry(payload, code="SYNC_PUSH_FAILED", exc=e)
            self._set_error(
                f"Push update failed for '{payload['sheet_name']}'",
                e,
                code="SYNC_PUSH_FAILED",
                context={"sheet_name": payload["sheet_name"], "obj_id": payload["obj_id"]},
            )

    def sync_all_to_sheets(self):
        """Force a full push of all local data to Google Sheets."""
        if not self.is_ready():
            return
        models = [User, Cycle, Goal, Objective, KeyResult, Task, CheckIn, WorkLog, Retrospective]
        with get_session_context() as session:
            for model_cls in models:
                try:
                    items = session.exec(select(model_cls)).all()
                    for item in items:
                        self.push_update(item)
                except Exception as e:
                    self._set_error(
                        f"Full sync failed for model '{model_cls.__name__}'",
                        e,
                        code="SYNC_FULL_PUSH_FAILED",
                        context={"model": model_cls.__name__},
                    )
        if self.retry_queue:
            self.process_retry_queue(force=True, max_items=200)

@st.cache_resource(show_spinner=False)
def get_sync_service():
    """Factory to get the singleton SheetSyncService with Streamlit caching."""
    return SheetSyncService()

