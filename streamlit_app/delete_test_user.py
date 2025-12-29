
from src.database import init_database, get_session_context
from src.models import User, Goal
from sqlmodel import select

def delete_user_and_data(target_username):
    init_database()
    with get_session_context() as session:
        # 1. Find User
        user = session.exec(select(User).where(User.username == target_username)).first()
        if not user:
            print(f"User '{target_username}' not found.")
            return

        print(f"Found User: {user.username} (ID: {user.id})")

        # 2. Find User's Goals
        goals = session.exec(select(Goal).where(Goal.owner_id == user.id)).all()
        print(f"Found {len(goals)} goals owned by user.")

        # 3. Delete Goals (Nodes) first - this triggers cascade for sub-nodes
        for g in goals:
            print(f"Deleting Goal: {g.title} (ID: {g.id})")
            session.delete(g)
        
        # 4. Delete User
        print(f"Deleting User: {user.username}")
        session.delete(user)
        
        # 5. Commit
        session.commit()
        print("Deletion complete.")

if __name__ == "__main__":
    delete_user_and_data("test_user_fix_2")
