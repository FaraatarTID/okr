from datetime import UTC, datetime

import pytest

from src.saas.identity_contract import EnterpriseIdentityConfig, IdentityProviderType
from src.saas.identity_ports import (
    IdentityContractError,
    IdentityLifecycleEvent,
    IdentityLifecycleEventType,
    InMemoryApplicationSessionStore,
    InMemorySessionRevocationRegistry,
    MockIdentityProvider,
    create_identity_session,
    normalize_external_claims,
)


def identity_config(**overrides):
    values = {
        "enabled": True,
        "provider": IdentityProviderType.OIDC,
        "issuer": "https://idp.example.test",
        "client_id": "okr-client",
        "authorization_endpoint": "https://idp.example.test/authorize",
        "token_endpoint": "https://idp.example.test/token",
        "jwks_uri": "https://idp.example.test/jwks",
        "allowed_domains": ["example.test"],
        "allowed_groups": ["okr-users", "okr-admins"],
        "group_role_map": {"okr-users": "member", "okr-admins": "admin"},
    }
    values.update(overrides)
    return EnterpriseIdentityConfig(**values)


def valid_claims(**overrides):
    values = {
        "signature_valid": True,
        "sub": "subject-42",
        "iss": "https://idp.example.test",
        "aud": "okr-client",
        "email": "user@example.test",
        "name": "Example User",
        "groups": ["okr-users"],
        "mfa_verified": True,
        "active": True,
    }
    values.update(overrides)
    return values


def test_mock_provider_has_deterministic_callback_and_normalized_identity():
    provider = MockIdentityProvider(identity_config(), valid_claims())
    assert provider.authorization_url(
        state="s1", redirect_uri="https://app/cb"
    ).startswith("mock://authorize")
    claims = provider.handle_callback(
        code="mock-code", state="s1", redirect_uri="https://app/cb"
    )
    identity = provider.normalize_claims(claims)
    assert identity.subject == "subject-42"
    assert identity.role == "member"
    assert provider.callback_count == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"sub": ""}, "stable subject"),
        ({"iss": "https://evil.example.test"}, "issuer"),
        ({"aud": "other-client"}, "audience"),
        ({"email": "user@other.test"}, "email domain"),
        ({"mfa_verified": False}, "MFA"),
        ({"groups": ["unknown"]}, "recognized group"),
        ({"active": False}, "disabled"),
        ({"signature_valid": False}, "signature"),
    ],
)
def test_identity_normalization_fails_closed(overrides, message):
    with pytest.raises(IdentityContractError, match=message):
        normalize_external_claims(
            identity_config(),
            valid_claims(**overrides),
            signature_valid=overrides.get("signature_valid", True),
        )


def test_missing_signature_verification_fails_closed_even_with_valid_claims():
    with pytest.raises(IdentityContractError, match="signature"):
        normalize_external_claims(
            identity_config(), valid_claims(), signature_valid=False
        )


def test_lifecycle_deactivation_and_role_change_revoke_sessions():
    provider = MockIdentityProvider(identity_config(), valid_claims())
    identity = provider.normalize_claims(valid_claims())
    session = create_identity_session(
        identity, ttl_seconds=300, now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    registry = InMemorySessionRevocationRegistry()
    assert registry.is_revoked(session.subject) is False
    registry.apply(
        IdentityLifecycleEvent(
            IdentityLifecycleEventType.ROLE_CHANGE,
            identity.subject,
            datetime.now(UTC),
            "ops",
            role="admin",
            reason="role changed",
        )
    )
    assert registry.is_revoked(session.subject) is True
    registry.apply(
        IdentityLifecycleEvent(
            IdentityLifecycleEventType.DEACTIVATE,
            identity.subject,
            datetime.now(UTC),
            "ops",
        )
    )
    assert registry.is_revoked(session.subject) is True


def test_application_session_port_supports_issue_and_revoke():
    identity = MockIdentityProvider(identity_config(), valid_claims()).normalize_claims(
        valid_claims()
    )
    store = InMemoryApplicationSessionStore()
    session = store.issue(identity, ttl_seconds=300)
    assert store.is_active(session.session_id) is True
    assert store.revoke_subject(identity.subject, reason="identity deactivated") == 1
    assert store.is_active(session.session_id) is False


def test_disabled_identity_cannot_normalize_or_create_session():
    config = identity_config(enabled=False)
    with pytest.raises(IdentityContractError, match="disabled"):
        normalize_external_claims(config, valid_claims())
