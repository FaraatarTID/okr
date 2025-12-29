import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from sqlmodel import Session, select, SQLModel
from sqlalchemy import text
import pandas as pd
from datetime import datetime
import json
import time

# Models to sync
# Models to sync
from src.models import (
    User, Cycle, Goal, Strategy, Objective, KeyResult, Initiative, Task, 
    WorkLog, CheckIn
)
from src.database import engine, get_session_context

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_NAME = "OKR_DB"

class SheetSyncService:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self._connect()

    def _connect(self):
        """Connect to Google Sheets API."""
        if "gcp_service_account" not in st.secrets:
            print("Sync Error: Missing gcp_service_account")
            return

        try:
            service_account_info = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            self.client = gspread.authorize(creds)
            
            try:
                self.spreadsheet = self.client.open(SPREADSHEET_NAME)
            except gspread.SpreadsheetNotFound:
                # Assuming user wants us to use the existing one or fail.
                # Auto-creation requires more permissions on folder, usually.
                print(f"Sync Error: Spreadsheet '{SPREADSHEET_NAME}' not found.")
        except Exception as e:
            print(f"Sync Connection Failed: {e}")

    def is_ready(self):
        return self.spreadsheet is not None

    def ensure_schema(self):
        """Ensure all required worksheets exist."""
        if not self.is_ready(): return

        required_sheets = [
            "Users", "Cycles", 
            "Goals", "Strategies", "Objectives", "KeyResults", "Initiatives", "Tasks",
            "CheckIns", "WorkLogs"
        ]
        
        try:
            existing_titles = [ws.title for ws in self.spreadsheet.worksheets()]
            
            for name in required_sheets:
                if name not in existing_titles:
                    try:
                        self.spreadsheet.add_worksheet(title=name, rows=100, cols=20)
                        print(f"Created missing worksheet: {name}")
                    except Exception as e:
                        print(f"Failed to create worksheet {name}: {e}")
        except Exception as e:
            print(f"Schema check failed: {e}")

    def restore_to_local_db(self):
        """
        Pull all data from Sheets and insert into local SQLite.
        Should be called on app startup.
        """
        if not self.is_ready(): return
        
        print("Restoring local database from Google Sheets...")
        self.ensure_schema()
        
        try:
            # 1. Base Tables (Order matters)
            self._restore_table(User, "Users")
            self._restore_table(Cycle, "Cycles")
            
            # 2. Hierarchy (Top-Down to satisfy FKs)
            self._restore_table(Goal, "Goals")
            self._restore_table(Strategy, "Strategies")
            self._restore_table(Objective, "Objectives")
            self._restore_table(KeyResult, "KeyResults")
            self._restore_table(Initiative, "Initiatives")
            self._restore_table(Task, "Tasks")
            
            # 3. Linked Tables
            self._restore_table(CheckIn, "CheckIns")
            self._restore_table(WorkLog, "WorkLogs")
            
            # 4. Legacy JSON Restore (Deprecated/Fallback)
            # self._restore_okr_trees()
            
            print("Database restoration complete.")
            
        except Exception as e:
            print(f"Critical Restore Error: {e}")

    def _restore_table(self, model_cls: SQLModel, sheet_name: str):
        """Generic helper to restore a single table."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            
            if not data:
                print(f"No data found in {sheet_name}, skipping.")
                return

            with get_session_context() as session:
                # Check what IDs already exist to avoid duplicates
                existing_ids = session.exec(select(model_cls.id)).all()
                existing_ids_set = set(existing_ids)
                
                count = 0
                for row in data:
                    # Convert types if necessary (Sheets returns str/int/float)
                    # We rely on Pydantic/SQLModel to coerce basic types, but dates need help
                    
                    # Skip if ID exists
                    if "id" in row and row["id"] in existing_ids_set:
                        continue
                        
                    # Handle DateTimes for specific fields
                    for field in ["created_at", "updated_at", "start_date", "end_date", "start_time", "end_time"]:
                        if field in row and row[field]:
                            try:
                                # Assume ISO format in Sheet
                                row[field] = datetime.fromisoformat(row[field])
                            except:
                                row[field] = None 

                    # Create object
                    # Remove empty strings for optional fields?
                    clean_row = {k: v for k, v in row.items() if v != ''}
                    
                    obj = model_cls.model_validate(clean_row)
                    session.add(obj)
                    count += 1
                
                session.commit()
                print(f"Restored {count} records to {model_cls.__tablename__}.")
                
        except Exception as e:
            print(f"Error restoring {sheet_name}: {e}")

    def push_update(self, model_obj, delete=False):
        """
        Push a single object change to the Sheet.
        Note: For simplicity/robustness in this phase, we might just append if new 
        or overwrite row if exists. 
        """
        if not self.is_ready(): return
        
        # Determine Sheet and Schema based on type
        # Determine Sheet and Schema based on type
        if isinstance(model_obj, User): sheet_name = "Users"
        elif isinstance(model_obj, Cycle): sheet_name = "Cycles"
        elif isinstance(model_obj, Goal): sheet_name = "Goals"
        elif isinstance(model_obj, Strategy): sheet_name = "Strategies"
        elif isinstance(model_obj, Objective): sheet_name = "Objectives"
        elif isinstance(model_obj, KeyResult): sheet_name = "KeyResults"
        elif isinstance(model_obj, Initiative): sheet_name = "Initiatives"
        elif isinstance(model_obj, Task): sheet_name = "Tasks"
        elif isinstance(model_obj, CheckIn): sheet_name = "CheckIns"
        elif isinstance(model_obj, WorkLog): sheet_name = "WorkLogs"
        else: return # Not a synced type

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            
            # Serialize
            data = model_obj.model_dump()
            # Serialize Datetimes
            for k, v in data.items():
                if isinstance(v, datetime):
                    data[k] = v.isoformat()
            
            # Check if exists (Naive search by ID)
            # Fetch all IDs (Column 1 usually)
            # CAUTION: This is slow for large datasets. 
            # Optimization: Cache IDs or use batch ops.
            
            # Headers?
            headers = worksheet.row_values(1)
            if not headers:
                # Write headers if empty
                headers = list(data.keys())
                worksheet.append_row(headers)
            
            # Map data to headers
            row_values = [data.get(h, "") for h in headers]
            
            existing_cell = worksheet.find(str(model_obj.id), in_column=1) # Assuming ID is col 1
            
            if delete:
                if existing_cell:
                    worksheet.delete_rows(existing_cell.row)
            else:
                if existing_cell:
                    # Update
                    # gspread update is cell-based or range-based.
                    # update row
                    # Determine range A{row}:Z{row}
                    # Helper: resize list to match headers
                    worksheet.update(range_name=f"A{existing_cell.row}", values=[row_values])
                else:
                    # Append
                    worksheet.append_row(row_values)
                    
        except Exception as e:
            print(f"Sync Push Error ({sheet_name}): {e}")

    def _restore_okr_trees(self):
        """
        Specialized restore for the main JSON sheet to populate SQL mirroring tables.
        """
        try:
            # Main sheet is the first one usually, or use a name if we had one
            from src.services.sheets_db import SheetsDB
            s_db = SheetsDB()
            if not s_db.is_connected(): return
            
            rows = s_db.get_all_rows()
            if not rows: return
            
            from utils.sync import sync_data_to_db
            
            for row in rows:
                username = row.get("username")
                json_data = row.get("data")
                if username and json_data:
                    try:
                        data = json.loads(json_data)
                        print(f"Syncing OKR Tree for {username} to SQL...")
                        sync_data_to_db(username, data)
                    except:
                        continue
        except Exception as e:
            print(f"Error restoring OKR trees: {e}")

# Singleton Instance
sync_service = SheetSyncService()
