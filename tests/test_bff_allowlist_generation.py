import json
from pathlib import Path

from scripts.generate_bff_allowlist import (
    ALLOWLIST_PATH,
    OPENAPI_PATH,
    POLICY_PATH,
    build_policy,
    render_allowlist,
)


def test_bff_policy_routes_exist_in_openapi_and_preserve_exclusions():
    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    policy = build_policy(schema, metadata)
    signatures = {
        (route["pathTemplate"], method)
        for route in policy["routes"]
        for method in route["methods"]
    }

    assert ("/v1/auth/login", "POST") in signatures
    assert ("/v1/auth/change-password", "POST") in signatures
    assert (
        next(
            route
            for route in policy["routes"]
            if route["pathTemplate"] == "/v1/auth/change-password"
        )["actorRequired"]
        is True
    )
    assert (
        next(
            route
            for route in policy["routes"]
            if route["pathTemplate"] == "/v1/auth/login"
        )["actorRequired"]
        is False
    )
    assert all(
        path
        not in {
            "/healthz",
            "/v1/admin/observability/metrics",
            "/v1/internal/session-registry/register",
            "/v1/internal/session-registry/revoke",
            "/v1/state/{key}",
        }
        for path, _method in signatures
    )

    assert all(
        ("/v1/internal/session-registry/" not in route["pathTemplate"])
        for route in metadata["routes"]
    )
    assert all(
        route["pathTemplate"] != "/v1/state/{key}" for route in metadata["routes"]
    )


def test_generator_refuses_a_policy_that_reintroduces_the_state_route():
    # The exclusion has to be enforced, not merely absent today: the entry was added once
    # before, most likely to satisfy the mutation-route coverage test, and would be again.
    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    metadata["routes"].append(
        {
            "pathTemplate": "/v1/state/{key}",
            "methods": ["GET", "POST"],
            "actorRequired": True,
        }
    )

    try:
        build_policy(schema, metadata)
    except ValueError as exc:
        assert "/v1/state/{key}" in str(exc)
    else:
        raise AssertionError("build_policy accepted the internal state route")


def test_generated_allowlist_is_current_and_deterministic():
    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy = build_policy(schema, metadata)

    assert ALLOWLIST_PATH.read_text(encoding="utf-8") == render_allowlist(policy)
    assert Path(ALLOWLIST_PATH).exists()
