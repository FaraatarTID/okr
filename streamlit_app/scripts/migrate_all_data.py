import os
import sys
import json

# Add parent directory to path to allow imports from streamlit_app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.storage import get_local_filename, load_data, load_all_data
from utils.sync import sync_data_to_db
from src.database import create_db_and_tables

import glob

def migrate():
    print("Starting Full Database Migration...")
    
    # 1. Ensure tables exist
    create_db_and_tables()
    
    # 2. Find all local JSON files
    pattern = "okr_data_*.json"
    files = glob.glob(pattern)
    print(f"Found {len(files)} data files.")
    
    # 3. For each user file, trigger a full sync
    for file_path in files:
        filename = os.path.basename(file_path)
        username = filename.replace("okr_data_", "").replace(".json", "")
        
        print(f"Syncing data for user: {username}...")
        try:
            # load_data handles merging from Sheets if connected
            data = load_data(username, force_refresh=True)
            sync_data_to_db(username, data)
            print(f"User {username} synced successfully.")
        except Exception as e:
            print(f"Failed to sync {username}: {e}")

    print("Migration Complete!")

if __name__ == "__main__":
    migrate()
