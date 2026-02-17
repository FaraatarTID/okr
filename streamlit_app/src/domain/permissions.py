"""
Role-Based Access Control (RBAC) and Permission verify logic.
"""
from enum import Enum
from typing import Any, Optional, Protocol

from src.models import User, UserRole, NodeBase, Team


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


def _is_team_manager(user: User, resource: ResourceProtocol, session: Any = None) -> bool:
    """Check if user is the manager of the resource's owner or team."""
    # 1. Direct team manager check (if team_id exists and we checked 'team.manager_id' - but Team doesn't have manager_id yet?)
    # The current model uses User.manager_id. User.team_id aligns users.
    # If resource.owner_id is a user managed by 'user', allow.
    
    if not resource.owner_id:
        return False
        
    # We need a session to resolve the owner's manager if not loaded.
    # For MVP, we assume permissions are checked with loaded objects or simple logic.
    # If we don't have the owner object loaded, we might need to fetch it.
    # But crud.py usually has the session.
    
    # Ideally, we pass the owner User object or session.
    # To keep this pure, we might need the resource to have owner loaded.
    pass 
    # Placeholder: detailed logic requires session queries which we want to keep out of pure domain if possible,
    # or pass session in.
    return False


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

    # Ownership check
    is_owner = (resource.owner_id == user.id)

    # Team Manager check
    # For now, we rely on the existing hierarchy logic: Manager of the Owner.
    # We need to fetch the owner to check their manager_id.
    is_manager_of_owner = False
    if user.role == UserRole.MANAGER and resource.owner_id and session:
        from src.models import User as DBUser
        owner = session.get(DBUser, resource.owner_id)
        if owner and owner.manager_id == user.id:
            is_manager_of_owner = True
            
    # Team checks (if resource belongs to user's team)
    is_same_team = (resource.team_id == user.team_id) if (resource.team_id and user.team_id) else False

    # MATRIX
    if action == Action.READ:
        # Member: Own + Public/Team info?
        # For MVP, strict: Own items only? Or Team items?
        # Current app: Members see only own. Managers see team.
        if is_owner: return True
        if user.role == UserRole.MANAGER and (is_manager_of_owner or is_same_team): return True
        return False

    if action in [Action.UPDATE, Action.DELETE]:
        # Member: Own items only.
        if is_owner: return True
        # Manager: Can update team member items?
        # Existing policy: "Manager... manage their assigned OKRs".
        # Usually managers can edit direct reports' OKRs.
        if user.role == UserRole.MANAGER and is_manager_of_owner: return True
        return False

    return False
