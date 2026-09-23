"""Typed contract for enterprise identity and provisioning integration."""

from __future__ import annotations

import base64
import hashlib
import hmac
from enum import StrEnum
from typing import Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IdentityProviderType(StrEnum):
    """Supported enterprise identity providers."""

    OIDC = "oidc"
    SAML = "saml"
    OKTA = "okta"
    MICROSOFT_ENTRA = "microsoft_entra"
    KEYCLOAK = "keycloak"
    CUSTOM = "custom"


class IdentityProvisioningMode(StrEnum):
    """Supported provisioning mode for user lifecycle automation."""

    NONE = "none"
    SCIM = "scim"


class EnterpriseIdentityConfig(BaseModel):
    """Identity contract for enterprise onboarding and lifecycle automation.

    This is intentionally a narrow contract: it defines the supported identity
    provider metadata and the required provisioning configuration. It does not
    implement SSO or SCIM transport logic; it only validates the enterprise
    identity configuration contract so later integration layers can share the same
    rules.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: IdentityProviderType = IdentityProviderType.OIDC
    issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_uri: str | None = None
    entity_id: str | None = None
    sso_url: str | None = None
    x509_certificate: str | None = None
    scim_mode: IdentityProvisioningMode = IdentityProvisioningMode.NONE
    scim_endpoint: str | None = None
    scim_token: str | None = None
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_groups: list[str] = Field(default_factory=list)
    group_role_map: dict[str, str] = Field(default_factory=dict)
    require_mfa: bool = True
    allow_local_passwords: bool = True

    @field_validator(
        "issuer",
        "client_id",
        "authorization_endpoint",
        "token_endpoint",
        "jwks_uri",
        "entity_id",
        "sso_url",
        "x509_certificate",
        "scim_endpoint",
        "scim_token",
    )
    @classmethod
    def reject_blank_optional_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not str(value).strip():
            raise ValueError("identity metadata must be non-empty text when provided")
        return str(value).strip()

    @field_validator("allowed_domains")
    @classmethod
    def normalize_allowed_domains(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for domain in value or []:
            text = str(domain).strip().lower()
            if not text:
                continue
            normalized.append(text)
        return normalized

    @field_validator("allowed_groups")
    @classmethod
    def normalize_allowed_groups(cls, value: list[str]) -> list[str]:
        return sorted(
            {str(item).strip().lower() for item in (value or []) if str(item).strip()}
        )

    @field_validator("group_role_map")
    @classmethod
    def normalize_group_role_map(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            str(group).strip().lower(): str(role).strip().lower()
            for group, role in (value or {}).items()
            if str(group).strip() and str(role).strip()
        }

    @model_validator(mode="after")
    def validate_required_enterprise_fields(self) -> "EnterpriseIdentityConfig":
        if not self.enabled:
            return self

        if self.provider in {
            IdentityProviderType.OIDC,
            IdentityProviderType.OKTA,
            IdentityProviderType.MICROSOFT_ENTRA,
            IdentityProviderType.KEYCLOAK,
            IdentityProviderType.CUSTOM,
        }:
            if not self.issuer:
                raise ValueError(
                    "issuer is required when enterprise identity is enabled"
                )
            if not self.client_id:
                raise ValueError(
                    "client_id is required when enterprise identity is enabled"
                )
            if self.provider in {
                IdentityProviderType.OIDC,
                IdentityProviderType.CUSTOM,
            }:
                if not self.authorization_endpoint:
                    raise ValueError(
                        "authorization_endpoint is required for OIDC-based enterprise login"
                    )
                if not self.token_endpoint:
                    raise ValueError(
                        "token_endpoint is required for OIDC-based enterprise login"
                    )
                if not self.jwks_uri:
                    raise ValueError(
                        "jwks_uri is required for OIDC-based enterprise login"
                    )

        if self.provider is IdentityProviderType.SAML:
            if not self.entity_id:
                raise ValueError("entity_id is required for SAML enterprise login")
            if not self.sso_url:
                raise ValueError("sso_url is required for SAML enterprise login")
            if not self.x509_certificate:
                raise ValueError(
                    "x509_certificate is required for SAML enterprise login"
                )

        if self.scim_mode is IdentityProvisioningMode.SCIM:
            if not self.scim_endpoint:
                raise ValueError(
                    "scim_endpoint is required when SCIM provisioning is enabled"
                )
            if not self.scim_token:
                raise ValueError(
                    "scim_token is required when SCIM provisioning is enabled"
                )

        if (
            self.enabled
            and self.allow_local_passwords is False
            and not self.allowed_domains
        ):
            # This is a deliberate operating policy: when enterprise SSO replaces the local sign-in
            # flow, the domain allowlist becomes mandatory as a guardrail to prevent broad account
            # takeover or accidental open access. The runtime can still accept explicitly approved
            # local-password exceptions if the operator opts in via allow_local_passwords=True.
            raise ValueError(
                "allowed_domains is required when enterprise identity is enabled and local passwords are disabled"
            )

        return self

    @property
    def is_enterprise_identity_active(self) -> bool:
        return bool(self.enabled)

    def email_domain_allowed(self, email: str) -> bool:
        """Return whether the provided email is permitted by the current enterprise policy."""

        if not email or not isinstance(email, str):
            return False
        normalized = email.strip().lower()
        if "@" not in normalized:
            return False
        domain = normalized.rsplit("@", 1)[1].strip()
        if not domain:
            return False
        return domain in set(self.allowed_domains)

    def validate_login_identifier(self, identifier: str) -> None:
        """Reject disallowed login identifiers for enterprise-only sign-in."""

        if not self.enabled:
            return
        if self.allow_local_passwords:
            return

        login = str(identifier or "").strip()
        if not login:
            raise ValueError("login identifier is required for enterprise sign-in")

        if "@" not in login:
            raise ValueError(
                "enterprise identity requires an email-style login identifier when local passwords are disabled"
            )

        if not self.email_domain_allowed(login):
            raise ValueError(
                "login identifier domain is not allowed by the configured enterprise identity policy"
            )

    def validate_oidc_metadata(
        self, *, http_client: httpx.Client | None = None
    ) -> dict[str, str]:
        """Fetch and validate discovery metadata for an OIDC identity provider."""

        if self.provider not in {
            IdentityProviderType.OIDC,
            IdentityProviderType.OKTA,
            IdentityProviderType.MICROSOFT_ENTRA,
            IdentityProviderType.KEYCLOAK,
            IdentityProviderType.CUSTOM,
        }:
            raise ValueError(
                "OIDC discovery is only valid for OIDC-compatible providers"
            )

        issuer = str(self.issuer or "").strip()
        if not issuer:
            raise ValueError("issuer is required when enterprise identity is enabled")

        discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
        client = http_client or httpx.Client(follow_redirects=True)
        owns_client = http_client is None
        try:
            response = client.get(discovery_url)
            if response.status_code != 200:
                raise ValueError(
                    f"OIDC discovery request failed for {issuer!r}: HTTP {response.status_code}"
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("OIDC discovery response must be a JSON object")
        finally:
            if owns_client:
                client.close()

        required_fields = {
            "issuer": issuer,
            "authorization_endpoint": self.authorization_endpoint,
            "token_endpoint": self.token_endpoint,
            "jwks_uri": self.jwks_uri,
        }
        for field_name, expected_value in required_fields.items():
            if not expected_value:
                continue
            actual_value = payload.get(field_name)
            if (
                not actual_value
                or str(actual_value).strip() != str(expected_value).strip()
            ):
                raise ValueError(
                    f"OIDC discovery metadata mismatch for {field_name}: "
                    f"expected {expected_value!r}, got {actual_value!r}"
                )

        if (
            self.issuer
            and payload.get("issuer")
            and str(payload["issuer"]).strip() != issuer
        ):
            raise ValueError(
                f"OIDC discovery issuer mismatch: expected {issuer!r}, got {payload.get('issuer')!r}"
            )

        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(value, str)
        }

    def exchange_authorization_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        state: str,
        http_client: httpx.Client | None = None,
    ) -> dict[str, str | int]:
        """Exchange OIDC authorization code for tokens and return the token payload."""

        if self.provider not in {
            IdentityProviderType.OIDC,
            IdentityProviderType.OKTA,
            IdentityProviderType.MICROSOFT_ENTRA,
            IdentityProviderType.KEYCLOAK,
            IdentityProviderType.CUSTOM,
        }:
            raise ValueError(
                "authorization-code exchange is only valid for OIDC-compatible providers"
            )

        token_endpoint = str(self.token_endpoint or "").strip()
        if not token_endpoint:
            raise ValueError(
                "token_endpoint is required for OIDC authorization-code exchange"
            )

        if not code or not redirect_uri or not state:
            raise ValueError(
                "code, redirect_uri, and state are required for OIDC authorization-code exchange"
            )

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "state": state,
            "client_id": self.client_id,
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        client = http_client or httpx.Client(follow_redirects=True)
        owns_client = http_client is None
        try:
            response = client.post(token_endpoint, data=payload, timeout=10.0)
            if response.status_code != 200:
                raise ValueError(
                    f"OIDC token exchange failed for {self.issuer!r}: HTTP {response.status_code}"
                )
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("OIDC token exchange response must be a JSON object")
        finally:
            if owns_client:
                client.close()

        access_token = body.get("access_token")
        if not access_token:
            raise ValueError(
                "OIDC token exchange response did not include an access_token"
            )

        return {
            str(key): value
            for key, value in body.items()
            if isinstance(value, (str, int))
        }

    def build_session_claims_from_id_token(
        self, claims: Mapping[str, object]
    ) -> dict[str, object]:
        """Translate a provider-issued OIDC claim set into app-session identity claims."""

        if self.provider not in {
            IdentityProviderType.OIDC,
            IdentityProviderType.OKTA,
            IdentityProviderType.MICROSOFT_ENTRA,
            IdentityProviderType.KEYCLOAK,
            IdentityProviderType.CUSTOM,
        }:
            raise ValueError(
                "session mapping is only defined for OIDC-compatible identity providers"
            )

        issuer = str(claims.get("iss") or "").strip()
        if issuer and self.issuer and issuer != self.issuer:
            raise ValueError(
                "ID token issuer does not match the configured enterprise issuer"
            )

        audience = claims.get("aud")
        if audience is not None and isinstance(audience, (list, tuple)):
            audience_values = {
                str(item).strip() for item in audience if str(item).strip()
            }
            if self.client_id and self.client_id not in audience_values:
                raise ValueError(
                    "ID token audience does not include the configured client_id"
                )
        elif (
            audience is not None
            and str(audience).strip()
            and self.client_id
            and str(audience).strip() != self.client_id
        ):
            raise ValueError(
                "ID token audience does not match the configured client_id"
            )

        email = str(claims.get("email") or "").strip()
        if not email:
            raise ValueError(
                "ID token must include an email claim for enterprise app session binding"
            )

        if self.enabled and not self.allow_local_passwords:
            self.validate_login_identifier(email)

        subject = str(claims.get("sub") or "").strip() or email
        username = email

        groups = claims.get("groups")
        if isinstance(groups, str):
            groups_list = [item.strip() for item in groups.split(",") if item.strip()]
        elif isinstance(groups, (list, tuple, set)):
            groups_list = [str(item).strip() for item in groups if str(item).strip()]
        else:
            groups_list = []

        normalized_groups = {group.lower() for group in groups_list}
        role = "member"
        if "atlas-admin" in normalized_groups or "admin" in normalized_groups:
            role = "admin"
        elif "atlas-manager" in normalized_groups or "manager" in normalized_groups:
            role = "manager"

        return {
            "actor": username,
            "username": username,
            "provider": self.provider.value,
            "subject": subject,
            "email": email,
            "email_verified": bool(claims.get("email_verified", False)),
            "name": str(claims.get("name") or email).strip(),
            "issuer": issuer or self.issuer or "",
            "aud": audience,
            "role": role,
            "roles": sorted(normalized_groups),
        }

    @staticmethod
    def _b64url_encode(value: str) -> str:
        return (
            base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
        )

    @staticmethod
    def _b64url_decode(value: str) -> str:
        padding = "=" * ((4 - len(value) % 4) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii")).decode(
            "utf-8"
        )

    def issue_app_session_token(
        self,
        *,
        claims: Mapping[str, object],
        secret: str,
        ttl_seconds: int,
        now_epoch_seconds: int | None = None,
    ) -> str:
        """Deprecated, non-authoritative compatibility issuer for ``oidc-session-v1``.

        The SPA BFF is the only supported session minter and verifier. This Python
        format remains unchanged only for compatibility characterization while
        external consumers are inventoried; it must not be used as an application
        session authority and is a candidate for removal after that inventory.
        """

        if not secret:
            raise ValueError("secret is required to issue an app session token")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        session_claims = self.build_session_claims_from_id_token(claims)
        effective_now = int(now_epoch_seconds if now_epoch_seconds is not None else 0)
        if effective_now <= 0:
            effective_now = int(__import__("time").time())
        expires_at = effective_now + int(ttl_seconds)
        payload = {
            "v": "oidc-session-v1",
            "iat": effective_now,
            "exp": expires_at,
            "expires_at": expires_at,
            "actor": session_claims["actor"],
            "username": session_claims["username"],
            "provider": session_claims["provider"],
            "subject": session_claims["subject"],
            "email": session_claims["email"],
            "email_verified": session_claims["email_verified"],
            "name": session_claims["name"],
            "issuer": session_claims["issuer"],
            "aud": session_claims["aud"],
            "role": session_claims.get("role", "member"),
            "roles": session_claims.get("roles", []),
        }
        payload_json = __import__("json").dumps(
            payload, separators=(",", ":"), sort_keys=True
        )
        payload_part = self._b64url_encode(payload_json)
        signature = hmac.new(
            secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"{payload_part}.{signature}"

    def verify_app_session_token(
        self,
        *,
        token: str,
        secret: str,
        now_epoch_seconds: int | None = None,
    ) -> dict[str, object]:
        """Deprecated, non-authoritative verifier for ``oidc-session-v1``.

        The SPA BFF is the only supported session minter and verifier. This Python
        verifier is retained only for compatibility characterization while external
        consumers are inventoried; it must not authorize application sessions and
        is a candidate for removal after that inventory.
        """

        if not token:
            raise ValueError("token is required")
        if not secret:
            raise ValueError("secret is required to verify an app session token")

        separator = token.rfind(".")
        if separator <= 0 or separator >= len(token) - 1:
            raise ValueError("invalid app session token format")

        payload_part, supplied_signature = token[:separator], token[separator + 1 :]
        expected_signature = hmac.new(
            secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError("invalid app session token signature")

        payload_json = self._b64url_decode(payload_part)
        try:
            payload = __import__("json").loads(payload_json)
        except ValueError as exc:
            raise ValueError("invalid app session token payload") from exc

        if not isinstance(payload, dict):
            raise ValueError("invalid app session token payload")

        expires_at = int(payload.get("exp", 0))
        effective_now = int(
            now_epoch_seconds
            if now_epoch_seconds is not None
            else __import__("time").time()
        )
        if expires_at <= effective_now:
            raise ValueError("app session token has expired")

        return payload

    def effective_policy_summary(self) -> dict[str, object]:
        """Return a compact summary for auditing and operational review."""

        return {
            "enabled": self.enabled,
            "provider": self.provider.value,
            "scim_mode": self.scim_mode.value,
            "require_mfa": self.require_mfa,
            "allow_local_passwords": self.allow_local_passwords,
            "allowed_domains": list(self.allowed_domains),
            "allowed_groups": list(self.allowed_groups),
            "group_role_map": dict(self.group_role_map),
        }


def load_enterprise_identity_config(
    env: Mapping[str, str] | None = None,
) -> EnterpriseIdentityConfig:
    """Build a typed enterprise identity config from environment variables."""

    values = dict(env or {})
    provider = str(values.get("OKR_IDENTITY_PROVIDER", "oidc")).strip().lower()
    enabled = str(
        values.get("OKR_ENTERPRISE_IDENTITY_ENABLED", "false")
    ).strip().lower() in {"1", "true", "yes", "on"}
    mode = str(values.get("OKR_PROVISIONING_MODE", "none")).strip().lower()
    if not provider:
        provider = IdentityProviderType.OIDC.value

    config = EnterpriseIdentityConfig(
        enabled=enabled,
        provider=provider,
        issuer=values.get("OKR_IDENTITY_ISSUER"),
        client_id=values.get("OKR_IDENTITY_CLIENT_ID"),
        client_secret=values.get("OKR_IDENTITY_CLIENT_SECRET"),
        authorization_endpoint=values.get("OKR_IDENTITY_AUTHORIZATION_ENDPOINT"),
        token_endpoint=values.get("OKR_IDENTITY_TOKEN_ENDPOINT"),
        jwks_uri=values.get("OKR_IDENTITY_JWKS_URI"),
        entity_id=values.get("OKR_IDENTITY_ENTITY_ID"),
        sso_url=values.get("OKR_IDENTITY_SSO_URL"),
        x509_certificate=values.get("OKR_IDENTITY_X509_CERTIFICATE"),
        scim_mode=mode,
        scim_endpoint=values.get("OKR_SCIM_ENDPOINT"),
        scim_token=values.get("OKR_SCIM_TOKEN"),
        allowed_domains=[
            domain
            for domain in str(values.get("OKR_ALLOWED_EMAIL_DOMAINS", "")).split(",")
            if domain.strip()
        ],
        allowed_groups=[
            group
            for group in str(values.get("OKR_ALLOWED_IDENTITY_GROUPS", "")).split(",")
            if group.strip()
        ],
        require_mfa=str(values.get("OKR_REQUIRE_MFA", "true")).strip().lower()
        in {"1", "true", "yes", "on"},
        allow_local_passwords=str(values.get("OKR_ALLOW_LOCAL_PASSWORDS", "false"))
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
    )
    return config


def enforce_enterprise_login_policy(
    identifier: str, *, env: Mapping[str, str] | None = None
) -> None:
    """Reject disallowed login identifiers when enterprise-only sign-in is configured."""

    config = load_enterprise_identity_config(env)
    if not config.enabled:
        return
    if config.allow_local_passwords:
        return
    config.validate_login_identifier(identifier)
