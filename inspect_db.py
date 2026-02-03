
import sqlite3
import os

db_path = os.path.join("streamlit_app", "okr_database.db")
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Table: objective ---")
    cursor.execute("PRAGMA table_info(objective)")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
        
    print("\n--- Migration Version ---")
    try:
        cursor.execute("SELECT * FROM alembic_version")
        print(cursor.fetchall())
    except:
        print("alembic_version table not found")
        
    conn.close()
