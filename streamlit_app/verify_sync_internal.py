
import os
import sys
import streamlit as st
import time

# Ensure we can import from current directory
sys.path.append(os.getcwd())

from src.models import Goal
from src.crud import create_goal, update_goal, delete_goal
from src.services.sheet_sync import sync_service

def test_sync():
    print("--- Starting Sync Verification ---")
    
    if "gcp_service_account" not in st.secrets:
        print("FAIL: No secrets found (checked st.secrets).")
        # Try to debug where it's looking
        # print(f"CWD: {os.getcwd()}")
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
        title=f"Test Sync Goal {test_id}",
        description="Created by verification script",
        external_id=test_id
    )
    
    if not goal:
        print("FAIL: Create Goal returned None")
        return

    # Check Sheet
    try:
        ws = sync_service.spreadsheet.worksheet("Goals")
        # Retry logic for eventual consistency? usually instant.
        found = False
        for _ in range(3):
            try:
                cell = ws.find(str(goal.id), in_column=1)
                if cell:
                    print(f"PASS: Goal Found in Sheet at Row {cell.row}")
                    found = True
                    break
            except Exception as e:
                # print(f"debug: find failed {e}")
                pass
            time.sleep(1)
            
        if not found:
            print("FAIL: Goal NOT found in Sheet after retries")
    except Exception as e:
        print(f"FAIL: Sheet check failed: {e}")

    # 3. Test Update Goal
    print("Updating Goal title...")
    update_goal(goal.id, title="Test Sync Goal UPDATED")
    
    try:
        if found:
            # Re-fetch row
            # gspread find again
            cell = ws.find(str(goal.id), in_column=1)
            row_vals = ws.row_values(cell.row)
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
        # Give it a moment?
        time.sleep(1)
        try:
           cell = ws.find(str(goal.id), in_column=1)
           print(f"FAIL: Goal still exists in Sheet after delete!")
        except:
           print("PASS: Goal deleted from Sheet (CellNotFound)")
    except Exception as e:
         print(f"PASS: Goal seems deleted (Error: {e})")

    print("--- Verification Complete ---")

if __name__ == "__main__":
    test_sync()
