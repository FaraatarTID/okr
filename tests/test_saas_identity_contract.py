import pytest

from src.saas.identity_contract import (
    EnterpriseIdentityConfig,
    IdentityProvisioningMode,
    IdentityProviderType,
    load_enterprise_identity_config,
)


def test_oidc_identity_contract_validates_required_metadata():
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
    )

    assert config.is_enterprise_identity_active is True
    assert config.provider is IdentityProviderType.OIDC


def test_oidc_identity_rejects_missing_issuer():
    with pytest.raises(ValueError, match="issuer"):
        EnterpriseIdentityConfig(
            enabled=True,
            provider=IdentityProviderType.OIDC,
            client_id="atlas-client",
            authorization_endpoint="https://idp.example.com/oauth2/authorize",
            token_endpoint="https://idp.example.com/oauth2/token",
            jwks_uri="https://idp.example.com/oauth2/jwks",
        )


def test_enterprise_policy_requires_domain_allowlist_when_local_passwords_disabled():
    with pytest.raises(ValueError, match="allowed_domains"):
        EnterpriseIdentityConfig(
            enabled=True,
            provider=IdentityProviderType.OIDC,
            issuer="https://idp.example.com/realms/acme",
            client_id="atlas-client",
            authorization_endpoint="https://idp.example.com/oauth2/authorize",
            token_endpoint="https://idp.example.com/oauth2/token",
            jwks_uri="https://idp.example.com/oauth2/jwks",
            allow_local_passwords=False,
            allowed_domains=[],
        )

    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    assert config.email_domain_allowed("user@example.com") is True
    assert config.email_domain_allowed("user@other.org") is False
    assert config.effective_policy_summary()["allow_local_passwords"] is False

    with pytest.raises(ValueError, match="domain is not allowed"):
        config.validate_login_identifier("user@other.org")

    config.validate_login_identifier("user@example.com")


def test_saml_identity_requires_sso_metadata():
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.SAML,
        entity_id="https://idp.example.com/entity",
        sso_url="https://idp.example.com/sso",
        x509_certificate="-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----",
    )

    assert config.enabled is True
    assert config.provider is IdentityProviderType.SAML


def test_scim_requires_both_endpoint_and_token():
    with pytest.raises(ValueError, match="scim_endpoint"):
        EnterpriseIdentityConfig(
            enabled=True,
            provider=IdentityProviderType.OIDC,
            issuer="https://idp.example.com/realms/acme",
            client_id="atlas-client",
            authorization_endpoint="https://idp.example.com/oauth2/authorize",
            token_endpoint="https://idp.example.com/oauth2/token",
            jwks_uri="https://idp.example.com/oauth2/jwks",
            scim_mode=IdentityProvisioningMode.SCIM,
            scim_token="super-secret",
        )

    with pytest.raises(ValueError, match="scim_token"):
        EnterpriseIdentityConfig(
            enabled=True,
            provider=IdentityProviderType.OIDC,
            issuer="https://idp.example.com/realms/acme",
            client_id="atlas-client",
            authorization_endpoint="https://idp.example.com/oauth2/authorize",
            token_endpoint="https://idp.example.com/oauth2/token",
            jwks_uri="https://idp.example.com/oauth2/jwks",
            scim_mode=IdentityProvisioningMode.SCIM,
            scim_endpoint="https://idp.example.com/scim",
        )


def test_load_enterprise_identity_config_reads_expected_env_values():
    config = load_enterprise_identity_config(
        {
            "OKR_ENTERPRISE_IDENTITY_ENABLED": "true",
            "OKR_IDENTITY_PROVIDER": "oidc",
            "OKR_IDENTITY_ISSUER": "https://idp.example.com/realms/acme",
            "OKR_IDENTITY_CLIENT_ID": "atlas-client",
            "OKR_IDENTITY_AUTHORIZATION_ENDPOINT": "https://idp.example.com/oauth2/authorize",
            "OKR_IDENTITY_TOKEN_ENDPOINT": "https://idp.example.com/oauth2/token",
            "OKR_IDENTITY_JWKS_URI": "https://idp.example.com/oauth2/jwks",
            "OKR_PROVISIONING_MODE": "scim",
            "OKR_SCIM_ENDPOINT": "https://idp.example.com/scim",
            "OKR_SCIM_TOKEN": "super-secret",
            "OKR_ALLOWED_EMAIL_DOMAINS": "example.com, acme.org",
            "OKR_REQUIRE_MFA": "true",
            "OKR_ALLOW_LOCAL_PASSWORDS": "false",
        }
    )

    assert config.enabled is True
    assert config.provider is IdentityProviderType.OIDC
    assert config.scim_mode is IdentityProvisioningMode.SCIM
    assert config.allowed_domains == ["example.com", "acme.org"]
    assert config.require_mfa is True
    assert config.allow_local_passwords is False


def test_oidc_discovery_validates_provider_metadata(monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "issuer": "https://idp.example.com/realms/acme",
                "authorization_endpoint": "https://idp.example.com/oauth2/authorize",
                "token_endpoint": "https://idp.example.com/oauth2/token",
                "jwks_uri": "https://idp.example.com/oauth2/jwks",
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.requested = []

        def get(self, url, *args, **kwargs):
            self.requested.append(url)
            return FakeResponse()

    fake_client = FakeClient()
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    monkeypatch.setattr(
        "src.saas.identity_contract.httpx.Client",
        lambda *args, **kwargs: fake_client,
    )

    payload = config.validate_oidc_metadata(http_client=fake_client)

    assert payload["issuer"] == "https://idp.example.com/realms/acme"
    assert fake_client.requested[0].endswith("/.well-known/openid-configuration")


def test_oidc_code_exchange_returns_session_tokens():
    class FakeTokenResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "access_token": "access-123",
                "id_token": "id-123",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "openid profile email",
            }

    class FakeClient:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, timeout=None):
            self.calls.append({"url": url, "data": data, "timeout": timeout})
            return FakeTokenResponse()

    fake_client = FakeClient()
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        client_secret="atlas-secret",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    result = config.exchange_authorization_code(
        code="auth-code-123",
        redirect_uri="https://app.example.com/callback",
        state="state-456",
        http_client=fake_client,
    )

    assert result["access_token"] == "access-123"
    assert result["token_type"] == "Bearer"
    assert fake_client.calls[0]["data"]["grant_type"] == "authorization_code"
    assert fake_client.calls[0]["data"]["code"] == "auth-code-123"
    assert fake_client.calls[0]["data"]["client_id"] == "atlas-client"
    assert (
        fake_client.calls[0]["data"]["redirect_uri"]
        == "https://app.example.com/callback"
    )


def test_oidc_id_token_maps_to_app_session_claims():
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    claims = config.build_session_claims_from_id_token(
        {
            "iss": "https://idp.example.com/realms/acme",
            "sub": "user-42",
            "aud": "atlas-client",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Example User",
        }
    )

    assert claims["actor"] == "user@example.com"
    assert claims["username"] == "user@example.com"
    assert claims["provider"] == "oidc"
    assert claims["subject"] == "user-42"
    assert claims["email_verified"] is True


def test_oidc_session_token_is_signed_and_verifiable():
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    token = config.issue_app_session_token(
        claims={
            "iss": "https://idp.example.com/realms/acme",
            "sub": "user-42",
            "aud": "atlas-client",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Example User",
        },
        secret="super-secret",
        ttl_seconds=3600,
        now_epoch_seconds=1700000000,
    )

    payload = config.verify_app_session_token(
        token=token, secret="super-secret", now_epoch_seconds=1700000100
    )

    assert payload["actor"] == "user@example.com"
    assert payload["provider"] == "oidc"
    assert payload["subject"] == "user-42"
    assert payload["expires_at"] == 1700003600
    assert payload["role"] == "member"


def test_oidc_session_claims_include_role_binding_from_idp_groups():
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    claims = config.build_session_claims_from_id_token(
        {
            "iss": "https://idp.example.com/realms/acme",
            "sub": "user-42",
            "aud": "atlas-client",
            "email": "user@example.com",
            "email_verified": True,
            "groups": ["atlas-admin", "atlas-manager"],
        }
    )

    assert claims["role"] == "admin"
    assert "atlas-admin" in claims["roles"]


def test_oidc_signed_session_token_contains_role_and_group_claims():
    config = EnterpriseIdentityConfig(
        enabled=True,
        provider=IdentityProviderType.OIDC,
        issuer="https://idp.example.com/realms/acme",
        client_id="atlas-client",
        authorization_endpoint="https://idp.example.com/oauth2/authorize",
        token_endpoint="https://idp.example.com/oauth2/token",
        jwks_uri="https://idp.example.com/oauth2/jwks",
        allow_local_passwords=False,
        allowed_domains=["example.com"],
    )

    token = config.issue_app_session_token(
        claims={
            "iss": "https://idp.example.com/realms/acme",
            "sub": "user-42",
            "aud": "atlas-client",
            "email": "user@example.com",
            "email_verified": True,
            "groups": ["atlas-admin", "atlas-manager"],
        },
        secret="super-secret",
        ttl_seconds=3600,
        now_epoch_seconds=1700000000,
    )

    payload = config.verify_app_session_token(
        token=token, secret="super-secret", now_epoch_seconds=1700000100
    )

    assert payload["role"] == "admin"
    assert "atlas-admin" in payload["roles"]
