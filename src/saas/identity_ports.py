"""Provider-neutral enterprise identity ports and test-only implementations.

These contracts deliberately stop at the application boundary.  They do not
perform OIDC/SAML discovery, token verification, SCIM calls, or production
identity provisioning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Mapping, Protocol
from uuid import uuid4

from src.saas.identity_contract import EnterpriseIdentityConfig


class IdentityContractError(ValueError):
    """Raised when an external identity cannot be admitted to the application."""


class IdentityLifecycleEventType(StrEnum):
    PROVISION = "provision"
    UPDATE = "update"
    DEACTIVATE = "deactivate"
    ROLE_CHANGE = "role_change"
    SESSION_REVOKED = "session_revoked"


@dataclass(frozen=True, slots=True)
class NormalizedExternalIdentity:
    """Stable identity data used after provider-specific validation."""

    subject: str
    issuer: str
    email: str
    display_name: str
    groups: tuple[str, ...]
    domain: str
    mfa_verified: bool
    role: str
    provider: str
    active: bool = True


@dataclass(frozen=True, slots=True)
class IdentitySession:
    session_id: str
    subject: str
    role: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False


class ApplicationSessionPort(Protocol):
    """Application-session creation, revocation, and active-state boundary."""

    def issue(
        self, identity: NormalizedExternalIdentity, *, ttl_seconds: int
    ) -> IdentitySession: ...

    def revoke(self, session_id: str, *, reason: str) -> bool: ...

    def is_active(self, session_id: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class IdentityLifecycleEvent:
    event_type: IdentityLifecycleEventType
    subject: str
    occurred_at: datetime
    actor: str
    role: str | None = None
    reason: str | None = None


class IdentityProviderPort(Protocol):
    """Provider-neutral authorization, callback, and claim-validation port."""

    def authorization_url(self, *, state: str, redirect_uri: str) -> str: ...

    def handle_callback(
        self, *, code: str, state: str, redirect_uri: str
    ) -> Mapping[str, Any]: ...

    def normalize_claims(
        self, claims: Mapping[str, Any]
    ) -> NormalizedExternalIdentity: ...


def normalize_external_claims(
    config: EnterpriseIdentityConfig,
    claims: Mapping[str, Any],
    *,
    signature_valid: bool = False,
) -> NormalizedExternalIdentity:
    """Validate and normalize claims, failing closed on every missing trust signal."""

    if not config.enabled:
        raise IdentityContractError("enterprise identity is disabled")
    if signature_valid is not True:
        raise IdentityContractError("external identity signature is not verified")

    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise IdentityContractError("external identity requires a stable subject")
    issuer = str(claims.get("iss") or "").strip()
    if not issuer or issuer != str(config.issuer or "").strip():
        raise IdentityContractError("external identity issuer is invalid")

    audience = claims.get("aud")
    audiences = (
        {str(item).strip() for item in audience}
        if isinstance(audience, (list, tuple, set))
        else {str(audience or "").strip()}
    )
    if not config.client_id or config.client_id not in audiences:
        raise IdentityContractError("external identity audience is invalid")

    email = str(claims.get("email") or "").strip().lower()
    if not email or "@" not in email or not config.email_domain_allowed(email):
        raise IdentityContractError("external identity email domain is not allowed")
    if config.require_mfa and claims.get("mfa_verified") is not True:
        raise IdentityContractError("external identity MFA signal is not verified")
    if claims.get("active", True) is not True:
        raise IdentityContractError("external identity is disabled or revoked")

    raw_groups = claims.get("groups", ())
    if isinstance(raw_groups, str):
        raw_groups = raw_groups.split(",")
    groups = tuple(
        sorted({str(item).strip().lower() for item in raw_groups if str(item).strip()})
    )
    allowed_groups = set(getattr(config, "allowed_groups", []))
    recognized_groups = allowed_groups or {
        "admin",
        "manager",
        "member",
        "atlas-admin",
        "atlas-manager",
        "atlas-member",
    }
    if not set(groups).intersection(recognized_groups):
        raise IdentityContractError("external identity has no recognized group")

    role_map = getattr(config, "group_role_map", {})
    default_role_map = {
        "admin": "admin",
        "atlas-admin": "admin",
        "manager": "manager",
        "atlas-manager": "manager",
        "member": "member",
        "atlas-member": "member",
    }
    effective_role_map = role_map or default_role_map
    mapped_roles = {
        effective_role_map[group] for group in groups if group in effective_role_map
    }
    if role_map and not mapped_roles:
        raise IdentityContractError("external identity has no recognized role mapping")
    role = sorted(mapped_roles)[0] if mapped_roles else "member"
    if role not in {"admin", "manager", "member"}:
        raise IdentityContractError("external identity role mapping is invalid")

    return NormalizedExternalIdentity(
        subject=subject,
        issuer=issuer,
        email=email,
        display_name=str(
            claims.get("name") or claims.get("display_name") or email
        ).strip(),
        groups=groups,
        domain=email.rsplit("@", 1)[1],
        mfa_verified=True,
        role=role,
        provider=config.provider.value,
    )


class MockIdentityProvider:
    """Deterministic, in-memory provider for conformance tests only."""

    def __init__(self, config: EnterpriseIdentityConfig, claims: Mapping[str, Any]):
        self.config = config
        self.claims = dict(claims)
        self.callback_count = 0

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        if not self.config.enabled:
            raise IdentityContractError("enterprise identity is disabled")
        if not state or not redirect_uri:
            raise IdentityContractError("state and redirect_uri are required")
        return f"mock://authorize?state={state}&redirect_uri={redirect_uri}"

    def handle_callback(
        self, *, code: str, state: str, redirect_uri: str
    ) -> Mapping[str, Any]:
        if code != "mock-code" or not state or not redirect_uri:
            raise IdentityContractError("mock callback is invalid")
        self.callback_count += 1
        return dict(self.claims)

    def normalize_claims(self, claims: Mapping[str, Any]) -> NormalizedExternalIdentity:
        return normalize_external_claims(
            self.config, claims, signature_valid=claims.get("signature_valid") is True
        )


class SessionRevocationPort(Protocol):
    def revoke_subject(self, subject: str, *, reason: str) -> None: ...

    def is_revoked(self, subject: str) -> bool: ...


@dataclass
class InMemorySessionRevocationRegistry:
    """Test/local registry proving lifecycle changes invalidate sessions."""

    _revoked: dict[str, str] = field(default_factory=dict)

    def revoke_subject(self, subject: str, *, reason: str) -> None:
        if not subject.strip() or not reason.strip():
            raise IdentityContractError(
                "session revocation requires subject and reason"
            )
        self._revoked[subject] = reason

    def is_revoked(self, subject: str) -> bool:
        return subject in self._revoked

    def apply(self, event: IdentityLifecycleEvent) -> None:
        if event.event_type in {
            IdentityLifecycleEventType.DEACTIVATE,
            IdentityLifecycleEventType.ROLE_CHANGE,
            IdentityLifecycleEventType.SESSION_REVOKED,
        }:
            self.revoke_subject(
                event.subject, reason=event.reason or event.event_type.value
            )


@dataclass
class InMemoryApplicationSessionStore:
    """Deterministic session store used by contract tests; never a production store."""

    _sessions: dict[str, IdentitySession] = field(default_factory=dict)

    def issue(
        self, identity: NormalizedExternalIdentity, *, ttl_seconds: int
    ) -> IdentitySession:
        session = create_identity_session(identity, ttl_seconds=ttl_seconds)
        self._sessions[session.session_id] = session
        return session

    def revoke(self, session_id: str, *, reason: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or not reason.strip():
            return False
        self._sessions[session_id] = IdentitySession(
            session.session_id,
            session.subject,
            session.role,
            session.issued_at,
            session.expires_at,
            revoked=True,
        )
        return True

    def revoke_subject(self, subject: str, *, reason: str) -> int:
        return sum(
            self.revoke(session_id, reason=reason)
            for session_id, session in list(self._sessions.items())
            if session.subject == subject
        )

    def is_active(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        return bool(
            session and not session.revoked and session.expires_at > datetime.now(UTC)
        )


def create_identity_session(
    identity: NormalizedExternalIdentity,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> IdentitySession:
    if not identity.active:
        raise IdentityContractError("cannot create a session for an inactive identity")
    if ttl_seconds <= 0:
        raise IdentityContractError("session TTL must be positive")
    issued_at = now or datetime.now(UTC)
    return IdentitySession(
        str(uuid4()),
        identity.subject,
        identity.role,
        issued_at,
        issued_at + timedelta(seconds=ttl_seconds),
    )
