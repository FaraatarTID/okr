from sqlmodel import Session, select
from src.models import KeyResult, Objective, LifecycleState
from src.database import get_engine


def verify_migration():
    engine = get_engine()
    with Session(engine) as session:
        # Check Objectives
        objectives = session.exec(select(Objective)).all()
        print(f"Found {len(objectives)} objectives.")
        for obj in objectives:
            # Check if state is loaded correctly and defaults to DRAFT (or whatever we set)
            # We set server default to DRAFT, checking if it reflects in model
            # logic: if we didn't wipe data, existing rows should have state=DRAFT
            if obj.state != LifecycleState.DRAFT:
                print(f"Objective {obj.id} has unexpected state: {obj.state}")
            # reflection can be None

        # Check Key Results
        krs = session.exec(select(KeyResult)).all()
        print(f"Found {len(krs)} key results.")
        for kr in krs:
            if kr.state != LifecycleState.DRAFT:
                print(f"KeyResult {kr.id} has unexpected state: {kr.state}")

            # Check if metric_type and weight are valid (not null)
            if kr.metric_type is None:
                print(f"KeyResult {kr.id} has NULL metric_type!")
            if kr.weight is None:
                print(f"KeyResult {kr.id} has NULL weight!")

    print("Verification complete.")


if __name__ == "__main__":
    verify_migration()
