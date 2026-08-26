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
    assert next(route for route in policy["routes"] if route["pathTemplate"] == "/v1/auth/login")[
        "actorRequired"
    ] is False
    assert all(
        path not in {"/healthz", "/v1/admin/observability/metrics"}
        for path, _method in signatures
    )


def test_generated_allowlist_is_current_and_deterministic():
    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy = build_policy(schema, metadata)

    assert ALLOWLIST_PATH.read_text(encoding="utf-8") == render_allowlist(policy)
    assert Path(ALLOWLIST_PATH).exists()