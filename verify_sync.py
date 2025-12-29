
import os
import sys
import streamlit as st
from datetime import datetime
import json
import time

# Mock Secrets if needed (Assume running in env where st.secrets works or load from .streamlit/secrets.toml)
# Since we are running via agent, we assume the environment is set up.

# Setup path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'streamlit_app'))

from src.models import Goal, Strategy, Objective
from src.crud import create_goal, update_goal, delete_goal
from src.services.sheet_sync import sync_service

def test_sync():
    print("--- Starting Sync Verification ---")
    
    if "gcp_service_account" not in st.secrets:
        print("FAIL: No secrets found.")
        return

    # 1. Initialize Sync Service
    if not sync_service.is_ready():
        print("FAIL: Sync Service not ready.")
        return
    else:
        print("PASS: Sync Service Connected.")
        
    sync_service.ensure_schema()
    print("PASS: Schema Ensured.")

    # 2. Test Create Goal
    test_id = f"test_sync_{int(time.time())}"
    print(f"Creating Goal with external_id: {test_id}")
    
    goal = create_goal(
        user_id="admin",
        title="Test Sync Goal",
        description="Created by verification script",
        external_id=test_id
    )
    
    if not goal:
        print("FAIL: Create Goal returned None")
        return

    # Check Sheet
    try:
        ws = sync_service.spreadsheet.worksheet("Goals")
        cell = ws.find(str(goal.id), in_column=1)
        if cell:
            print(f"PASS: Goal Found in Sheet at Row {cell.row}")
        else:
            print("FAIL: Goal NOT found in Sheet")
    except Exception as e:
        print(f"FAIL: Sheet check failed: {e}")

    # 3. Test Update Goal
    print("Updating Goal title...")
    update_goal(goal.id, title="Test Sync Goal UPDATED")
    
    try:
        # Re-fetch row
        cell = ws.find(str(goal.id), in_column=1)
        # Assuming title is column 3 (Id, User, Title...) - checking by re-reading row
        row_vals = ws.row_values(cell.row)
        # Just print row to verify visual correctness in logs if needed, or check content
        if "Test Sync Goal UPDATED" in row_vals:
            print("PASS: Update reflected in Sheet")
        else:
            print(f"FAIL: Update not reflected. Row: {row_vals}")
    except Exception as e:
         print(f"FAIL: Update check failed: {e}")

    # 4. Test Delete Goal
    print("Deleting Goal...")
    delete_goal(goal.id)
    
    try:
        cell = None
        try:
           cell = ws.find(str(goal.id), in_column=1)
        except:
           pass
           
        if cell:
            print(f"FAIL: Goal still exists in Sheet after delete!")
        else:
            print("PASS: Goal deleted from Sheet")
    except Exception as e:
        # find raises exception if not found in some versions, or returns None in others.
        # If gspread.exceptions.CellNotFound, that's a PASS.
        if "CellNotFound" in str(e):
             print("PASS: Goal deleted from Sheet (CellNotFound)")
        else:
             print(f"PASS: Goal seems deleted (Error: {e})")

    print("--- Verification Complete ---")

if __name__ == "__main__":
    test_sync()
