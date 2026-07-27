"""Static contract and policy constants for CRUD-layer boundaries."""

from __future__ import annotations

import os

# Field allow-lists are explicit mutation contracts. Update helpers validate
# incoming kwargs against these sets to prevent silent schema drift.
ALLOWED_GOAL_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "cycle_id",
    "strategy_tags",
    "is_expanded",
    "deadline",
}
ALLOWED_OBJECTIVE_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "score_mode",
    "weight",
    "is_expanded",
    "deadline",
    "state",
    "final_reflection",
}
ALLOWED_KEY_RESULT_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "start_value",
    "target_value",
    "current_value",
    "metric_type",
    "unit",
    "weight",
    "initiative_tags",
    "ai_analysis",
    "is_expanded",
    "deadline",
    "state",
    "final_reflection",
}
ALLOWED_TASK_UPDATE_KWARGS = {
    "description",
    "progress",
    "deadline",
    "assignee_id",
    "is_expanded",
}
ALLOWED_EXPERIMENT_UPDATE_FIELDS = {
    "hypothesis",
    "change_description",
    "start_at",
    "end_at",
    "status",
    "decision",
    "decision_rationale",
    "expected_effect_direction",
    "expected_effect_size",
}

# Sentinel used where `None` is a valid user value and we still need to detect
# "argument omitted" semantics (for example partial updates).
UNSET = object()

# Authentication throttling policy defaults (overridable by env vars).
AUTH_USER_WINDOW_SECONDS = max(1, int(os.getenv("AUTH_USER_WINDOW_SECONDS", "300")))
AUTH_USER_MAX_ATTEMPTS = max(1, int(os.getenv("AUTH_USER_MAX_ATTEMPTS", "5")))
AUTH_IP_WINDOW_SECONDS = max(1, int(os.getenv("AUTH_IP_WINDOW_SECONDS", "300")))
AUTH_IP_MAX_ATTEMPTS = max(1, int(os.getenv("AUTH_IP_MAX_ATTEMPTS", "20")))
AUTH_LOCKOUT_SECONDS = max(1, int(os.getenv("AUTH_LOCKOUT_SECONDS", "900")))

# Bootstrap retry policy for first-run admin creation.
ADMIN_BOOTSTRAP_MAX_RETRIES = max(1, int(os.getenv("ADMIN_BOOTSTRAP_MAX_RETRIES", "3")))
ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS = max(
    0.0, float(os.getenv("ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS", "0.4"))
)

BOOTSTRAP_ADMIN_PASSWORD_ENV = "OKR_BOOTSTRAP_ADMIN_PASSWORD"

MODEL_BINDING_NAMES = (
    "Goal",
    "Objective",
    "KeyResult",
    "Task",
    "WorkLog",
    "TaskStatus",
    "DashboardGoal",
    "TaskWithTimer",
    "Cycle",
    "CheckIn",
    "User",
    "UserRole",
    "WeeklyPlan",
    "Retrospective",
    "AuthThrottleState",
    "Team",
    "LifecycleState",
    "AlignmentEdge",
    "AlignmentType",
    "VariationType",
    "ExperimentStatus",
    "ExperimentDecision",
    "ExpectedEffectDirection",
    "Experiment",
    "RetroExperimentOutcome",
)
