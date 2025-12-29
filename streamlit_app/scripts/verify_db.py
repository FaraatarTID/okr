import os
import sys
from sqlmodel import Session, select, func

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import engine
from src.models import Goal, Strategy, Objective, KeyResult, Initiative, Task, WorkLog

def verify():
    print("Verifying Database Population...")
    models = [Goal, Strategy, Objective, KeyResult, Initiative, Task, WorkLog]
    
    with Session(engine) as session:
        for model in models:
            count = session.exec(select(func.count()).select_from(model)).one()
            print(f"{model.__name__}: {count} records")

if __name__ == "__main__":
    verify()
