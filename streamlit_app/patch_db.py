import sqlite3
import os

DB_PATH = "okr_database.db"

def patch_db():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check/Add assignee_id to task
    try:
        cursor.execute("ALTER TABLE task ADD COLUMN assignee_id INTEGER")
        print("Column 'assignee_id' added to 'task'.")
    except Exception as e:
        print(f"Result for task.assignee_id: {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    patch_db()
