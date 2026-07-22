from conftest import utc_now_naive


def test_audit_query_helpers_filter_by_actor_role_team_and_target_type(isolated_db):
    from src.audit import audit_log
    from src.audit_queries import count_audit_events, list_audit_events
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

        alice = User(
            username="alice",
            password_hash="hash",
            role=UserRole.MANAGER,
            team_id=alpha.id,
        )
        bob = User(
            username="bob",
            password_hash="hash",
            role=UserRole.MEMBER,
            team_id=beta.id,
        )
        session.add(alice)
        session.add(bob)
        session.commit()
        session.refresh(alice)
        session.refresh(bob)

    with observability_context(correlation_id="corr-1", request_id="req-1"):
        audit_log(
            action="create",
            entity="weekly_plan",
            actor="alice",
            target_type="weekly_plan",
            target_id=11,
            target_owner_id=alice.id,
            target_team_id=alpha.id,
            details={"success": True, "weekly_plan_id": 11},
        )
    with observability_context(correlation_id="corr-2", request_id="req-2"):
        audit_log(
            action="analyze",
            entity="ai_node",
            actor="bob",
            target_type="node",
            target_id=99,
            target_owner_id=bob.id,
            target_team_id=beta.id,
            details={"success": True, "node_id": 99},
        )

    with get_session_context() as session:
        manager_rows = list_audit_events(
            session,
            actor_role="manager",
            actor_team_id=alpha.id,
            target_type="weekly_plan",
        )
        manager_count = count_audit_events(
            session,
            actor_role="manager",
            actor_team_id=alpha.id,
            target_type="weekly_plan",
        )
        node_rows = list_audit_events(session, target_type="node")
        corr_rows = list_audit_events(session, correlation_id="corr-2")

    assert manager_count == 1
    assert len(manager_rows) == 1
    assert manager_rows[0].actor == "alice"
    assert manager_rows[0].actor_role == "manager"
    assert manager_rows[0].target_type == "weekly_plan"
    assert int(manager_rows[0].target_id) == 11
    assert int(manager_rows[0].target_owner_id) == int(alice.id)
    assert len(node_rows) == 1
    assert node_rows[0].actor == "bob"
    assert node_rows[0].target_type == "node"
    assert len(corr_rows) == 1
    assert corr_rows[0].request_id == "req-2"
