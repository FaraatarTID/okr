"""
Role-Based Access Control (RBAC) and Permission verify logic.
"""
from enum import Enum
from typing import Any, Optional, Protocol

from src.models import User, UserRole


class ResourceProtocol(Protocol):
    """Protocol for resources that have ownership fields."""
    id: Optional[int]
    owner_id: Optional[int]
    team_id: Optional[int]


class Action(str, Enum):
    """Actions that can be performed on resources."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE_TEAM = "manage_team"


def _is_owner(user: User, resource: ResourceProtocol) -> bool:
    """Check if user owns the resource."""
    return resource.owner_id == user.id


def can_track_task_by_owner(
    *,
    actor_user_id: Optional[int],
    task_owner_id: Optional[int],
) -> bool:
    """
    Backward-compatible wrapper around centralized timer policy.

    Canonical policy implementation now lives in `src.domain.authorization`.
    """
    from src.domain.authorization import can_track_task_timer

    return can_track_task_timer(
        actor_user_id=actor_user_id,
        timer_owner_user_id=task_owner_id,
    )


def _is_team_manager(user: User, resource: ResourceProtocol, session: Any = None) -> bool:
    """Check if user is the manager of the resource's owner or team."""
    if user.role != UserRole.MANAGER or user.id is None:
        return False

    owner_id = getattr(resource, "owner_id", None)
    if owner_id is None:
        return False
    try:
        owner_id = int(owner_id)
    except (TypeError, ValueError):
        return False

    if owner_id == int(user.id):
        return False

    owner = getattr(resource, "owner", None)
    if owner is not None:
        return bool(
            getattr(owner, "is_active", True)
            and getattr(owner, "manager_id", None) == user.id
        )

    if session is None:
        return False

    owner_row = session.get(User, owner_id)
    if not owner_row:
        return False
    return bool(owner_row.is_active and owner_row.manager_id == user.id)


def check_permission(
    user: User,
    action: Action,
    resource: Optional[ResourceProtocol] = None,
    session: Any = None
) -> bool:
    """
    Central permission checker.
    
    Args:
        user: The actor attempting the action.
        action: The action being attempted.
        resource: The target resource (optional for global actions like CREATE).
        session: Database session (optional, for resolving relations).
        
    Returns:
        bool: True if allowed, False otherwise.
    """
    if not user.is_active:
        return False

    # 1. Admin superuser
    if user.role == UserRole.ADMIN:
        return True

    # 2. Global CREATE permissions
    if action == Action.CREATE:
        # Everyone can create? Or restricted?
        # Usually everyone can create tasks/KRs if they own the parent?
        # Creation context is usually "Create UNDER parent".
        # So 'resource' here should be the PARENT node if applicable, or None for top-level Goal.
        
        # Creating a Goal:
        if resource is None: 
            # Top level creation.
            # Managers and Admins can create Goals? Members?
            # Existing app allows everyone to create goals if they own them.
            return True
        else:
            # Creation under a parent (resource is parent).
            # Check if user can UPDATE the parent to add children.
            return check_permission(user, Action.UPDATE, resource, session)

    # 3. Resource-specific permissions
    if resource is None:
        # Action requires a resource but none provided
        return False

    is_owner = _is_owner(user, resource)
    is_manager_of_owner = _is_team_manager(user, resource, session=session)

    # Team checks (if resource belongs to user's team)
    is_same_team = (
        resource.team_id == user.team_id
        if (resource.team_id is not None and user.team_id is not None)
        else False
    )

    # MATRIX
    if action == Action.READ:
        # Member: Own + Public/Team info?
        # For MVP, strict: Own items only? Or Team items?
        # Current app: Members see only own. Managers see team.
        if is_owner:
            return True
        if user.role == UserRole.MANAGER and (is_manager_of_owner or is_same_team):
            return True
        return False

    if action in [Action.UPDATE, Action.DELETE]:
        # Member: Own items only.
        if is_owner:
            return True
        # Manager: Can update team member items?
        # Existing policy: "Manager... manage their assigned OKRs".
        # Usually managers can edit direct reports' OKRs.
        if user.role == UserRole.MANAGER and is_manager_of_owner:
            return True
        return False

    return False
