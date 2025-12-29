import os
import sys
from sqlmodel import SQLModel

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import engine
# Important: Import models so they are registered with metadata
import src.models 

def purge():
    print("Purging all OKR tables...")
    try:
        SQLModel.metadata.drop_all(engine)
        print("Database purged successfully.")
    except Exception as e:
        print(f"Error purging database: {e}")

if __name__ == "__main__":
    purge()
