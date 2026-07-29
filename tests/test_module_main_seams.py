import importlib
import sys

from fastapi import FastAPI


def _import_main_with_dev_profile(monkeypatch):
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("OKR_RUN_IDEMPOTENCY_CHECKS", "false")

    sys.modules.pop("backend_app.main", None)
    return importlib.import_module("backend_app.main")


def _snapshot_routes(module) -> set[tuple[str, str]]:
    return {(route.path, ",".join(sorted(route.methods or []))) for route in module.app.routes}


def test_main_app_factory_contract(monkeypatch):
    main = _import_main_with_dev_profile(monkeypatch)

    app = main.create_app()
    app_reloaded = main.create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "OKR Internal Backend"
    assert app.version == "0.1.0"

    # Public app factory contract should remain stable for deployment/runtime entry points.
    assert callable(main.create_app)
    assert main.app is not app
    assert app_reloaded is not app
    assert main.app.title == "OKR Internal Backend"
    assert len(app.routes) == len(app_reloaded.routes)


def test_main_app_import_idempotence(monkeypatch):
    first = _import_main_with_dev_profile(monkeypatch)
    first_routes = len(first.app.routes)

    # Re-import by reload should preserve public surface and app composition contract.
    second = importlib.reload(first)
    second_routes = len(second.app.routes)

    assert second.app.title == "OKR Internal Backend"
    assert second_routes == first_routes
    assert second is first


def test_main_wrappers_route_through_helper_modules(monkeypatch):
    main = _import_main_with_dev_profile(monkeypatch)
    observed = {}

    def fake_coerce_int(value, *, field_name):
        observed["coerce"] = (value, field_name)
        return 7

    monkeypatch.setattr(
        main, "_coerce_int_impl", fake_coerce_int
    )
    result = main._coerce_int("x", field_name="n")
    assert result == 7
    assert observed == {"coerce": ("x", "n")}

    def fake_pick_primary_active_cycle(cycles):
        observed["pick"] = tuple(cycles)
        return {"id": 1}

    monkeypatch.setattr(
        "backend_app.main_runtime_helpers._pick_primary_active_cycle_impl",
        fake_pick_primary_active_cycle,
    )
    assert main._pick_primary_active_cycle([{"id": 1}]) == {"id": 1}
    assert observed["pick"] == ({"id": 1},)

    def fake_payload(kind, params, actor, *, main: object, allowed_kinds):
        observed["payload"] = (kind, actor, tuple(sorted(allowed_kinds)))
        return {"read_kind": kind, "main_module_name": main.__name__, "actor": actor}

    monkeypatch.setattr(main, "_read_query_payload_impl", fake_payload)
    response = main._read_query_payload(
        kind="cycle_summary",
        params={"cycle_id": 3},
        actor="user-a",
    )
    assert response["read_kind"] == "cycle_summary"
    assert response["actor"] == "user-a"
    assert response["main_module_name"] == "backend_app.main"
    assert observed["payload"][0] == "cycle_summary"
    assert observed["payload"][1] == "user-a"


def test_main_seam_contract_expected_exports(monkeypatch):
    main = _import_main_with_dev_profile(monkeypatch)

    required_exports = {
        "create_app",
        "app",
        "_coerce_int",
        "_pick_primary_active_cycle",
        "_resolve_scope_for_actor",
        "_read_query_payload",
        "api_create_goal",
        "api_update_experiment",
        "get_observability_metrics_snapshot",
        "_resolve_actor_scope",
    }
    for symbol in required_exports:
        assert hasattr(main, symbol), f"missing seam symbol: {symbol}"
        assert callable(getattr(main, symbol))


def test_main_route_contract_is_env_stable(monkeypatch):
    main = _import_main_with_dev_profile(monkeypatch)
    dev_routes = _snapshot_routes(main)

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "postgres")
    monkeypatch.setenv("OKR_RUN_IDEMPOTENCY_CHECKS", "true")
    sys.modules.pop("backend_app.main", None)
    prod_main = importlib.import_module("backend_app.main")
    prod_routes = _snapshot_routes(prod_main)

    assert len(prod_routes) == len(dev_routes)
    assert dev_routes == prod_routes
    assert prod_main.app.title == "OKR Internal Backend"


def test_main_bootstrap_helpers_are_single_hop(monkeypatch):
    main = _import_main_with_dev_profile(monkeypatch)

    observed: list[str] = []

    monkeypatch.setattr(main, "init_database", lambda: observed.append("init_database"))
    monkeypatch.setattr(main, "ensure_admin_exists", lambda: (observed.append("ensure_admin_exists"), True)[1])

    assert main._bootstrap_init_database() is None
    assert main._bootstrap_ensure_admin_exists() is True
    assert observed == ["init_database", "ensure_admin_exists"]


def test_main_runtime_seam_functions_delegate(monkeypatch):
    main = _import_main_with_dev_profile(monkeypatch)

    observed: list[tuple[str, tuple]] = []

    def _fake_resolve_scope_for_actor_impl(actor: str, token_version=None):
        observed.append(("resolve_scope", (actor, token_version)))
        return {"scope": actor, "token_version": token_version}

    def _fake_resolve_actor_scope_impl(session, actor_username, token_version=None):
        observed.append(("resolve_actor_scope", (session, actor_username, token_version)))
        return {"actor": actor_username, "token_version": token_version}

    monkeypatch.setattr(
        main,
        "_resolve_scope_for_actor_impl",
        _fake_resolve_scope_for_actor_impl,
    )
    monkeypatch.setattr(
        main,
        "_resolve_actor_scope_impl",
        _fake_resolve_actor_scope_impl,
    )

    assert main._resolve_scope_for_actor("member-1", token_version=3) == {
        "scope": "member-1",
        "token_version": 3,
    }
    assert main._resolve_actor_scope(
        session=object(),
        actor_username="member-2",
        token_version=4,
    ) == {"actor": "member-2", "token_version": 4}

    assert ("resolve_scope", ("member-1", 3)) in observed
    assert any(call[0] == "resolve_actor_scope" for call in observed)
