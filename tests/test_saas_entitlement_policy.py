from src.saas.entitlement_policy import ActorKind, EntitlementPolicy, SubscriptionPlan


def test_pre_saas_policy_is_unlimited_and_callable_from_any_path():
    policy = EntitlementPolicy.pre_saas()
    assert policy.check_feature("future-billing-feature").allowed is True
    assert policy.check_quota("users", 10_000).allowed is True


def test_enforced_plan_separates_customer_admin_and_platform_operator():
    from src.saas.entitlement_policy import EntitlementContext

    policy = EntitlementPolicy(
        EntitlementContext(
            actor_kind=ActorKind.CUSTOMER_ADMIN,
            plan=SubscriptionPlan.ENTERPRISE,
            features=frozenset({"audit"}),
            quotas={"users": 2},
            enforcement_enabled=True,
        )
    )
    assert policy.check_feature("audit", actor=ActorKind.CUSTOMER_ADMIN).allowed is True
    assert (
        policy.check_feature("billing", actor=ActorKind.CUSTOMER_ADMIN).allowed is False
    )
    assert policy.check_quota("users", 2).allowed is False
    assert (
        policy.check_feature("billing", actor=ActorKind.PLATFORM_OPERATOR).allowed
        is True
    )
    assert (
        EntitlementPolicy.require_platform_operator(ActorKind.CUSTOMER_ADMIN).allowed
        is False
    )
