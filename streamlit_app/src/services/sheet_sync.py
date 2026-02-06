import streamlit as st
from sqlmodel import Session, select, SQLModel
from sqlalchemy import text
import pandas as pd
from datetime import datetime
import json
import time

# Models to sync
from src.models import (
    User, Cycle, Goal, Objective, KeyResult, Task, 
    WorkLog, CheckIn, Retrospective
)
from src.database import engine, get_session_context
from src.config import is_production

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
        self.spreadsheet_name = st.secrets.get("GCP_SPREADSHEET_NAME", "OKR_DB")
        self._connect()

    def _set_error(self, message, exc=None):
        """Record and surface sync errors for diagnostics."""
        if exc:
            message = f"{message}: {exc}"
        self.last_error = message
        print(f"[SheetSync] {message}")

    def _connect(self):
        """Connect to Google Sheets API."""
        self.last_error = None
        if is_production():
            self.last_error = "Google Sheets sync is disabled in production mode."
            return
        if "gcp_service_account" not in st.secrets:
            self.last_error = "Missing gcp_service_account in secrets"
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
                self.last_error = f"Spreadsheet '{self.spreadsheet_name}' not found"
            except Exception as e:
                self.last_error = f"Failed to open '{self.spreadsheet_name}': {str(e)}"
        except Exception as e:
            self.last_error = f"Connection Failed: {str(e)}"

    def is_ready(self):
        """Check if the sync service is connected and ready."""
        return self.client is not None and self.spreadsheet is not None

    def get_last_error(self):
        """Return the last connection or sync error."""
        return self.last_error

    def reconnect(self):
        """Manually trigger a reconnection attempt."""
        self._connect()
        return self.is_ready()

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
                        existing_map[r.id] = ts
                except Exception as e:
                    self._set_error(f"Failed to read local rows for '{sheet_name}'", e)

                for row in data:
                    clean_row = {k: v for k, v in row.items() if v != ''}
                    
                    # Parse sheet timestamp
                    sheet_ts = None
                    if "updated_at" in clean_row and clean_row["updated_at"]:
                        try: sheet_ts = datetime.fromisoformat(clean_row["updated_at"])
                        except: pass
                    
                    # Convert dates
                    for field in ["created_at", "updated_at", "start_date", "end_date", "deadline"]:
                        if field in clean_row and clean_row[field]:
                             try: clean_row[field] = datetime.fromisoformat(clean_row[field])
                             except: pass

                    # Check existence
                    obj_id = clean_row.get("id")
                    if obj_id in existing_map:
                        local_ts = existing_map[obj_id]
                        if sheet_ts and local_ts and sheet_ts > local_ts:
                            local_obj = session.get(model_cls, obj_id)
                            for k, v in clean_row.items():
                                if hasattr(local_obj, k):
                                    setattr(local_obj, k, v)
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
        if not self.is_ready(): return
        
        sheet_name = getattr(model_obj, "__tablename__", None)
        if not sheet_name:
            if isinstance(model_obj, User): sheet_name = "Users"
            elif isinstance(model_obj, Cycle): sheet_name = "Cycles"
            elif isinstance(model_obj, Goal): sheet_name = "Goals"
            elif isinstance(model_obj, Objective): sheet_name = "Objectives"
            elif isinstance(model_obj, KeyResult): sheet_name = "KeyResults"
            elif isinstance(model_obj, Task): sheet_name = "Tasks"
            elif isinstance(model_obj, CheckIn): sheet_name = "CheckIns"
            elif isinstance(model_obj, WorkLog): sheet_name = "WorkLogs"
            elif isinstance(model_obj, Retrospective): sheet_name = "Retrospectives"
            else: return

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            data = model_obj.model_dump()
            obj_id = str(data.get("id"))
            
            # Serialize Datetimes
            for k, v in data.items():
                if isinstance(v, datetime):
                    data[k] = v.isoformat()
            
            # Get Headers
            headers = worksheet.row_values(1)
            if not headers:
                headers = list(data.keys())
                worksheet.append_row(headers)
            
            row_values = [data.get(h, "") for h in headers]
            if sheet_name not in self.id_cache:
                self.id_cache[sheet_name] = self._get_id_map(worksheet)
            
            row_num = self.id_cache[sheet_name].get(obj_id)
            
            if delete:
                if row_num:
                    worksheet.delete_rows(row_num)
                    del self.id_cache[sheet_name]
            else:
                if row_num:
                    worksheet.update(range_name=f"A{row_num}", values=[row_values])
                else:
                    worksheet.append_row(row_values)
                    del self.id_cache[sheet_name]
        except Exception as e:
            self._set_error(f"Push update failed for '{sheet_name}'", e)

    def sync_all_to_sheets(self):
        """Force a full push of all local data to Google Sheets."""
        if not self.is_ready(): return
        models = [User, Cycle, Goal, Objective, KeyResult, Task, CheckIn, WorkLog, Retrospective]
        with get_session_context() as session:
            for model_cls in models:
                try:
                    items = session.exec(select(model_cls)).all()
                    for item in items:
                        self.push_update(item)
                except Exception as e:
                    self._set_error(f"Full sync failed for model '{model_cls.__name__}'", e)

@st.cache_resource(show_spinner=False)
def get_sync_service():
    """Factory to get the singleton SheetSyncService with Streamlit caching."""
    return SheetSyncService()

