from sqlmodel import select, text
from src.database import get_session_context
from src.models import User, Team


def smoke_test():
    print("Starting smoke test...")
    try:
        with get_session_context() as session:
            print("Database connected.")

            # 1. Verify Team table exists and query it
            teams = session.exec(select(Team)).all()
            print(f"Teams found: {len(teams)}")

            # 2. Verify User table has team_id column
            # We can just query a user and access .team_id
            user = session.exec(select(User)).first()
            if user:
                print(f"User found: {user.username}, team_id: {user.team_id}")
            else:
                print("No users found (might be fresh DB).")

            # 3. Verify Goal table has owner_id
            # Query raw SQL to check column existence if needed, or ORM access
            try:
                session.exec(
                    text(
                        "SELECT owner_id, team_id, created_by, updated_by FROM goal LIMIT 1"
                    )
                )
                print(
                    "Goal table has new columns (owner_id, team_id, created_by, updated_by)."
                )
            except Exception as e:
                print(f"Error checking Goal columns: {e}")
                return False

            print("Smoke test PASSED.")
            return True
    except Exception as e:
        print(f"Smoke test FAILED: {e}")
        return False


if __name__ == "__main__":
    smoke_test()
