"""`validate_forwarded_role_claims` must not skip a check it could not perform.

A supplied role claim is only meaningful if it is compared with the actor's current
role. When that role cannot be established, the claim is unverified, so the request
must be rejected instead of silently accepted.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend_app.security import validate_forwarded_role_claims


def test_no_claim_supplied_skips_the_check_without_resolving_scope(monkeypatch) -> None:
    import backend_app.scope_resolution as scopes

    def _fail(*_args, **_kwargs):
        raise AssertionError("scope must not be resolved when no claim is supplied")

    monkeypatch.setattr(scopes, "_resolve_scope_for_actor", _fail)

    validate_forwarded_role_claims(
        actor="alice", x_okr_role=None, x_okr_roles=None, scope=None
    )


def test_no_actor_skips_the_check() -> None:
    validate_forwarded_role_claims(
        actor=None, x_okr_role="admin", x_okr_roles=None, scope=None
    )


def test_claim_is_rejected_when_scope_lookup_fails(monkeypatch) -> None:
    import backend_app.scope_resolution as scopes

    def _boom(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(scopes, "_resolve_scope_for_actor", _boom)

    with pytest.raises(HTTPException) as exc:
        validate_forwarded_role_claims(
            actor="alice", x_okr_role="admin", x_okr_roles=None, scope=None
        )
    assert exc.value.status_code == 503


def test_lookup_http_errors_are_propagated_unchanged(monkeypatch) -> None:
    import backend_app.scope_resolution as scopes

    def _stale(*_args, **_kwargs):
        raise HTTPException(status_code=401, detail="Session token version is stale.")

    monkeypatch.setattr(scopes, "_resolve_scope_for_actor", _stale)

    with pytest.raises(HTTPException) as exc:
        validate_forwarded_role_claims(
            actor="alice", x_okr_role="member", x_okr_roles=None, scope=None
        )
    assert exc.value.status_code == 401


@pytest.mark.parametrize("scope", [{}, {"role": ""}, {"role": None}, {"role": "  "}])
def test_claim_is_rejected_when_actor_has_no_role(scope) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_forwarded_role_claims(
            actor="alice", x_okr_role="admin", x_okr_roles=None, scope=scope
        )
    assert exc.value.status_code == 403


def test_roles_claim_is_rejected_when_actor_has_no_role() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_forwarded_role_claims(
            actor="alice", x_okr_role=None, x_okr_roles="atlas-admin", scope={}
        )
    assert exc.value.status_code == 403


def test_matching_claim_is_accepted() -> None:
    validate_forwarded_role_claims(
        actor="alice",
        x_okr_role="member",
        x_okr_roles="atlas-member",
        scope={"role": "member"},
    )


def test_mismatched_claim_is_still_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_forwarded_role_claims(
            actor="alice",
            x_okr_role="admin",
            x_okr_roles=None,
            scope={"role": "member"},
        )
    assert exc.value.status_code == 403
