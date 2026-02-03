
import sqlite3
import os

db_path = os.path.join("streamlit_app", "okr_database.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def check_table(table_name):
    print(f"--- Table: {table_name} ---")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
    print("")

check_table("goal")
check_table("objective")
check_table("key_result")
check_table("task")

conn.close()
