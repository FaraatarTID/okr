from __future__ import annotations

from scripts import check_spa_api_contract_boundary


def test_repository_spa_api_modules_use_the_contract_boundary() -> None:
    assert check_spa_api_contract_boundary.main() == 0


def test_boundary_checker_rejects_handwritten_generated_response_contracts(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text(
        "export interface NodeMutationResponse { id: number }\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_newer_handwritten_generated_response_contracts(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text(
        "export interface AiStrategyPulseResponse { summary: string }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_direct_backend_fetches(tmp_path, monkeypatch) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (api / "unsafe.ts").write_text(
        'fetch("/api/backend/v1/read/query")\n', encoding="utf-8"
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_nested_or_constructed_backend_fetches(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    nested = api / "nested"
    nested.mkdir(parents=True)
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (nested / "unsafe.tsx").write_text(
        'const base = "/api/backend"; fetch(`${base}/v1/read/query`)\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_global_fetch_and_fetch_aliases(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (api / "unsafe.ts").write_text(
        "const request = globalThis.fetch; request('/api/backend/v1/read/query')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_bracket_notation_fetch_aliases(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (api / "unsafe.ts").write_text(
        'const request = globalThis["fetch"]; request("/api/backend/v1/read/query")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_direct_fetches_outside_api_wrappers(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "src"
    api = source / "lib" / "api"
    component = source / "components"
    api.mkdir(parents=True)
    component.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (component / "unsafe.tsx").write_text(
        'fetch("/api/backend/v1/read/query")\n', encoding="utf-8"
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "SPA_SOURCE_DIR", source)
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_the_legacy_untyped_helper(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (api / "unsafe.ts").write_text(
        "backendFetch('/api/backend/v1/read/query')\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_duplicate_response_types_outside_types_module(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (api / "admin.ts").write_text(
        "export type AdminAiHealthResponse = { status: string };\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_unknown_handwritten_response_contracts(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text(
        "export interface FutureBackendResponse { id: string }\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    assert check_spa_api_contract_boundary.main() == 1


def test_boundary_checker_rejects_operations_not_exposed_by_the_bff(
    tmp_path, monkeypatch
) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "http.ts").write_text("", encoding="utf-8")
    (api / "types.ts").write_text("export type Safe = string\n", encoding="utf-8")
    (api / "unsafe.ts").write_text(
        'backendJsonRequest({ operation: "undocumented_for_bff" })\n',
        encoding="utf-8",
    )
    openapi = tmp_path / "openapi.json"
    openapi.write_text(
        '{"paths": {"/v1/safe": {"get": {"operationId": "safe_operation"}}}}',
        encoding="utf-8",
    )
    policy = tmp_path / "route-policy.json"
    policy.write_text(
        '{"routes": [{"pathTemplate": "/v1/safe", "methods": ["GET"]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_spa_api_contract_boundary, "API_DIR", api)
    monkeypatch.setattr(check_spa_api_contract_boundary, "TRANSPORT", api / "http.ts")
    monkeypatch.setattr(check_spa_api_contract_boundary, "OPENAPI_PATH", openapi)
    monkeypatch.setattr(check_spa_api_contract_boundary, "BFF_POLICY_PATH", policy)
    assert check_spa_api_contract_boundary.main() == 1
