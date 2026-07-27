def test_summarize_audit_events_groups_by_actor_role_team_and_target(isolated_db):
    from src.audit import audit_log
    from src.audit_queries import summarize_audit_events
    from src.database import get_session_context
    from src.models import Team, User, UserRole
    from src.observability import observability_context

    with get_session_context() as session:
        alpha = Team(name="Alpha")
        beta = Team(name="Beta")
        session.add(alpha)
        session.add(beta)
        session.commit()
        session.refresh(alpha)
        session.refresh(beta)

        admin = User(
            username="alice",
            password_hash="hash",
            role=UserRole.ADMIN,
            team_id=alpha.id,
        )
        member = User(
            username="bob",
            password_hash="hash",
            role=UserRole.MEMBER,
            team_id=beta.id,
        )
        session.add(admin)
        session.add(member)
        session.commit()
        session.refresh(admin)
        session.refresh(member)

    with observability_context(correlation_id="corr-1", request_id="req-1"):
        audit_log(
            action="create",
            entity="weekly_plan",
            actor="alice",
            target_type="weekly_plan",
            target_id=10,
            target_owner_id=admin.id,
            target_team_id=alpha.id,
            details={"success": True, "weekly_plan_id": 10},
        )

    with observability_context(correlation_id="corr-2", request_id="req-2"):
        audit_log(
            action="analyze",
            entity="ai_node",
            actor="bob",
            target_type="node",
            target_id=99,
            target_owner_id=member.id,
            target_team_id=beta.id,
            details={"success": False, "node_id": 99},
        )

    with get_session_context() as session:
        summary = summarize_audit_events(session, days=30, recent_limit=10)

    assert summary["window_days"] == 30
    assert summary["total_events"] == 2
    assert summary["success_events"] == 1
    assert summary["failure_events"] == 1
    assert {item["value"] for item in summary["by_actor_role"]} == {"admin", "member"}
    assert {item["value"] for item in summary["by_target_type"]} == {
        "weekly_plan",
        "node",
    }
    assert len(summary["recent_events"]) == 2
