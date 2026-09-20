"""Pure commercial policy contracts, disabled for the current pre-SaaS profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ActorKind(StrEnum):
    CUSTOMER_ADMIN = "customer_admin"
    PLATFORM_OPERATOR = "platform_operator"
    MEMBER = "member"


class SubscriptionPlan(StrEnum):
    PRE_SAAS = "pre_saas"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True, slots=True)
class EntitlementContext:
    actor_kind: ActorKind
    plan: SubscriptionPlan = SubscriptionPlan.PRE_SAAS
    features: frozenset[str] = frozenset()
    quotas: dict[str, int | None] = field(default_factory=dict)
    enforcement_enabled: bool = False


@dataclass(frozen=True, slots=True)
class EntitlementDecision:
    allowed: bool
    reason: str


class EntitlementPolicy:
    """One policy callable for UI, API, and worker paths."""

    def __init__(self, context: EntitlementContext):
        self.context = context

    def check_feature(
        self, feature: str, *, actor: ActorKind | None = None
    ) -> EntitlementDecision:
        if not feature.strip():
            return EntitlementDecision(False, "feature is required")
        if not self.context.enforcement_enabled:
            return EntitlementDecision(
                True, "pre-SaaS entitlement enforcement is disabled"
            )
        if actor is ActorKind.PLATFORM_OPERATOR:
            return EntitlementDecision(True, "platform operator policy access")
        if actor is ActorKind.CUSTOMER_ADMIN and feature in self.context.features:
            return EntitlementDecision(True, "feature is enabled for the plan")
        return EntitlementDecision(False, "feature is not entitled")

    def check_quota(self, quota: str, usage: int) -> EntitlementDecision:
        if usage < 0:
            return EntitlementDecision(False, "usage cannot be negative")
        limit = self.context.quotas.get(quota)
        if not self.context.enforcement_enabled or limit is None:
            return EntitlementDecision(
                True, "quota enforcement is disabled or unlimited"
            )
        return EntitlementDecision(
            usage < limit, "within quota" if usage < limit else "quota exceeded"
        )

    @staticmethod
    def pre_saas(
        actor_kind: ActorKind = ActorKind.CUSTOMER_ADMIN,
    ) -> "EntitlementPolicy":
        return EntitlementPolicy(
            EntitlementContext(actor_kind=actor_kind, enforcement_enabled=False)
        )

    @staticmethod
    def require_platform_operator(actor_kind: ActorKind) -> EntitlementDecision:
        return EntitlementDecision(
            actor_kind is ActorKind.PLATFORM_OPERATOR, "platform operator required"
        )
