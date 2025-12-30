
import sys
import os
from sqlalchemy import text
sys.path.append(os.getcwd())
from src.database import get_session_context

def migrate():
    print("Migrating Database Schema...")
    with get_session_context() as session:
        # Check if column exists to avoid error? 
        # SQLite doesn't have "IF NOT EXISTS" for ADD COLUMN in older versions, but usually safe to try/catch
        try:
            session.exec(text("ALTER TABLE task ADD COLUMN start_date DATETIME"))
            session.commit()
            print("Successfully added 'start_date' column to 'task' table.")
        except Exception as e:
            if "duplicate column name" in str(e):
                print("Column 'start_date' already exists.")
            else:
                print(f"Migration Error: {e}")

if __name__ == "__main__":
    migrate()
