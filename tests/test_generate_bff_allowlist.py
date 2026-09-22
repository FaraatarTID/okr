from __future__ import annotations

import pytest

from scripts.generate_bff_allowlist import build_policy


def test_bff_policy_rejects_a_route_without_a_documented_openapi_operation() -> None:
    schema = {"paths": {"/v1/jobs": {"post": {}}}}
    policy = {
        "routes": [
            {"pathTemplate": "/v1/jobs", "methods": ["POST"], "actorRequired": True}
        ]
    }
    with pytest.raises(ValueError, match="lack OpenAPI operation IDs"):
        build_policy(schema, policy)
