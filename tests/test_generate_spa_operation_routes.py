from __future__ import annotations

from scripts.generate_spa_operation_routes import render


def test_operation_manifest_uses_openapi_method_path_and_parameter_schema() -> None:
    manifest = render(
        {
            "paths": {
                "/v1/widgets/{widget_id}": {
                    "patch": {
                        "operationId": "update_widget",
                        "parameters": [
                            {
                                "name": "widget_id",
                                "in": "path",
                                "schema": {"type": "integer"},
                            }
                        ],
                    }
                }
            }
        }
    )
    assert (
        '"update_widget": { method: "PATCH", pathTemplate: "/v1/widgets/{widget_id}" }'
        in manifest
    )
    assert '"update_widget": `/v1/widgets/${number}`;' in manifest


def test_operation_manifest_limits_public_operations_to_bff_policy() -> None:
    manifest = render(
        {
            "paths": {
                "/v1/public": {"get": {"operationId": "public_operation"}},
                "/v1/internal": {"get": {"operationId": "internal_operation"}},
            }
        },
        {"public_operation"},
    )
    assert '"public_operation",' in manifest
    assert (
        '"internal_operation",' not in manifest.split("BFF_PUBLIC_OPERATION_IDS", 1)[1]
    )
