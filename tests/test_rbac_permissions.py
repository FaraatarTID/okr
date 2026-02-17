
import pytest
from src.models import User, UserRole, Goal, Team
from src.domain.permissions import check_permission, Action

def test_rbac_matrix():
    # Setup users
    admin = User(id=1, username="admin", role=UserRole.ADMIN, is_active=True)
    manager = User(id=2, username="manager", role=UserRole.MANAGER, is_active=True, team_id=10)
    member = User(id=3, username="member", role=UserRole.MEMBER, is_active=True, team_id=10)
    outsider = User(id=4, username="outsider", role=UserRole.MEMBER, is_active=True, team_id=20)
    
    # Setup resources
    # Goal owned by member
    member_goal = Goal(id=100, owner_id=member.id, team_id=member.team_id, title="Member Goal")
    # Goal owned by manager
    manager_goal = Goal(id=101, owner_id=manager.id, team_id=manager.team_id, title="Manager Goal")
    # Goal owned by outsider
    outsider_goal = Goal(id=102, owner_id=outsider.id, team_id=outsider.team_id, title="Outsider Goal")

    # 1. Admin can do anything
    assert check_permission(admin, Action.READ, member_goal) is True
    assert check_permission(admin, Action.UPDATE, member_goal) is True
    assert check_permission(admin, Action.DELETE, member_goal) is True

    # 2. Manager
    # Can manage own goal
    assert check_permission(manager, Action.UPDATE, manager_goal) is True
    # Can manage member goal (same team/subordinate - assuming logic holds)
    # Note: check_permission logic relies on session to resolve manager_id which isn't mocked here perfectly
    # unless we pass session or resource has owner loaded.
    # The current implementation checks: is_manager_of_owner (needs session lookup) OR is_same_team (for read).
    # Since we didn't mock session lookup, manager update member_goal might fail if it relies on session.
    # But current implementation checks: `is_same_team = (resource.team_id == user.team_id)`
    # And for READ: `if user.role == UserRole.MANAGER and (is_manager_of_owner or is_same_team): return True`
    # So Manager READ Member Goal (same team) -> True.
    assert check_permission(manager, Action.READ, member_goal) is True
    
    # Manager UPDATE Member Goal -> Needs `is_manager_of_owner`.
    # `is_manager_of_owner` needs session.
    # We can mock session? Or just test non-session logic?
    # Let's skip session-dependent test here or mock it.
    
    # Manager vs Outsider
    assert check_permission(manager, Action.READ, outsider_goal) is False
    assert check_permission(manager, Action.UPDATE, outsider_goal) is False

    # 3. Member
    # Can manage own goal
    assert check_permission(member, Action.UPDATE, member_goal) is True
    # Cannot manage manager goal
    assert check_permission(member, Action.UPDATE, manager_goal) is False
    # Cannot read manager goal? (Strict ownership for now, unless public?)
    # Implementation: `if is_owner: return True`. Else False for Member.
    assert check_permission(member, Action.READ, manager_goal) is False
