"""
Domain logic for OKR lifecycle states (Draft, Active, Grading, Archived).
"""
from typing import List, Set, Dict
from src.models import LifecycleState

# Allowed transitions for a state machine approach
ALLOWED_TRANSITIONS: Dict[LifecycleState, Set[LifecycleState]] = {
    LifecycleState.DRAFT: {LifecycleState.ACTIVE},
    LifecycleState.ACTIVE: {LifecycleState.GRADING, LifecycleState.DRAFT},
    LifecycleState.GRADING: {LifecycleState.ARCHIVED, LifecycleState.ACTIVE},
    LifecycleState.ARCHIVED: {LifecycleState.ACTIVE}, # Allow recovery if needed
}

def validate_transition(current_state: LifecycleState, next_state: LifecycleState) -> bool:
    """Check if a transition between states is allowed."""
    if current_state == next_state:
        return True
    return next_state in ALLOWED_TRANSITIONS.get(current_state, set())

def get_allowed_transitions(current_state: LifecycleState) -> List[LifecycleState]:
    """Return a list of states that can be transitioned to from the current state."""
    return list(ALLOWED_TRANSITIONS.get(current_state, set()))

def get_state_color(state: LifecycleState) -> str:
    """Return a color hex for the state UI."""
    colors = {
        LifecycleState.DRAFT: "#9E9E9E",    # Gray
        LifecycleState.ACTIVE: "#2196F3",   # Blue
        LifecycleState.GRADING: "#FF9800",  # Orange
        LifecycleState.ARCHIVED: "#607D8B", # Blue Grey
    }
    return colors.get(state, "#000000")

STATE_HINTS: Dict[LifecycleState, str] = {
    LifecycleState.DRAFT: "Drafting phase. Objective is not yet being tracked for progress.",
    LifecycleState.ACTIVE: "Active phase. Progress and scoring are currently tracked.",
    LifecycleState.GRADING: "Quarterly review. Reflection and final scoring adjustment time.",
    LifecycleState.ARCHIVED: "Closed. Read-only historical record.",
}

STATE_ICONS: Dict[LifecycleState, str] = {
    LifecycleState.DRAFT: "📝",
    LifecycleState.ACTIVE: "🚀",
    LifecycleState.GRADING: "⚖️",
    LifecycleState.ARCHIVED: "📁",
}

def cascade_state_change(objective_state: LifecycleState) -> LifecycleState:
    """Determine the child KR state based on the parent Objective state."""
    # Simple mapping: KRs usually follow the Objective
    return objective_state
