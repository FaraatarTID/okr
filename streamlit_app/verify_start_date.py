
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from src.database import get_session_context
from src.crud import create_task, update_task, get_node_by_external_id
from src.models import Task, Initiative, KeyResult
from sqlmodel import select

def verify_start_date():
    print("Verifying Start Date Feature...")
    
    start_dt = datetime.utcnow() + timedelta(days=2)
    # Truncate to microseconds to match DB precision if needed, but eq check usually handles it.
    # SQLite might lose some precision?
    
    with get_session_context() as session:
        # 1. Find a parent
        init = session.exec(select(Initiative)).first()
        kr = session.exec(select(KeyResult)).first()
        
        parent_init = init.id if init else None
        parent_kr = kr.id if kr else None
        
        if not parent_init and not parent_kr:
            print("No parent (Initiative or KR) found. Cannot test create_task.")
            # Try to find existing task to update
            existing_task = session.exec(select(Task)).first()
            if existing_task:
                 print(f"Testing Update on Task {existing_task.id}")
                 updated = update_task(existing_task.id, start_date=start_dt)
                 assert updated.start_date is not None
                 # simple check
                 print("Update successful.")
            else:
                 print("No data to test.")
            return

        print(f"Creating task with start_date: {start_dt}")
        new_task = create_task(
            initiative_id=parent_init, 
            key_result_id=parent_kr if not parent_init else None,
            title="Test Start Date Task", 
            start_date=start_dt
        )
        
        print(f"Created Task {new_task.id} with start_date: {new_task.start_date}")
        assert new_task.start_date is not None
        
        # Verify persistence by re-fetching
        persisted_task = session.get(Task, new_task.id)
        assert persisted_task.start_date is not None
        # Compare dates (ignoring timezone/microsecond diffs for simplicity)
        print(f"Persisted Start Date: {persisted_task.start_date}")
        assert persisted_task.start_date.date() == start_dt.date()
        print("SUCCESS: Start Date Persisted.")

if __name__ == "__main__":
    verify_start_date()
