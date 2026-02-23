from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.ui import components_bridge_helpers


def test_build_orchestrator_context_uses_components_runtime():
    class _Context:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    orchestrator = SimpleNamespace(AtlasWorkspaceOrchestratorContext=_Context)
    fake_st = SimpleNamespace(session_state={"k": "v"})
    components_module = SimpleNamespace(
        atlas_workspace_orchestrator_helpers=orchestrator,
        st=fake_st,
        logger="logger",
    )

    context = components_bridge_helpers._build_orchestrator_context(
        components_module=components_module,
        username="alice",
        deps="deps",
    )

    assert context.kwargs["st_module"] is fake_st
    assert context.kwargs["session_state"] == {"k": "v"}
    assert context.kwargs["username"] == "alice"
    assert context.kwargs["logger"] == "logger"
    assert context.kwargs["deps"] == "deps"


def test_render_atlas_workspace_from_components_builds_and_dispatches(monkeypatch):
    calls: dict[str, object] = {}
    components_module = SimpleNamespace(
        atlas_workspace_orchestrator_helpers=SimpleNamespace(
            render_atlas_workspace_with_context=lambda context: (
                calls.setdefault("context", context),
                "done",
            )[1]
        )
    )

    monkeypatch.setattr(
        components_bridge_helpers,
        "_resolve_timer_mutations",
        lambda: ("start", "stop"),
    )
    monkeypatch.setattr(
        components_bridge_helpers,
        "_build_orchestrator_deps",
        lambda **kwargs: (calls.setdefault("deps_kwargs", kwargs), "deps")[1],
    )
    monkeypatch.setattr(
        components_bridge_helpers,
        "_build_orchestrator_context",
        lambda **kwargs: (calls.setdefault("ctx_kwargs", kwargs), "ctx")[1],
    )

    result = components_bridge_helpers.render_atlas_workspace_from_components(
        components_module=components_module,
        username="alice",
    )

    assert result == "done"
    assert calls["deps_kwargs"]["components_module"] is components_module
    assert calls["deps_kwargs"]["start_timer_fn"] == "start"
    assert calls["deps_kwargs"]["stop_timer_fn"] == "stop"
    assert calls["ctx_kwargs"]["username"] == "alice"
    assert calls["ctx_kwargs"]["deps"] == "deps"
    assert calls["context"] == "ctx"


def test_cached_get_leadership_metrics_prefers_backend_success(monkeypatch):
    backend_calls = {}
    backend_module = ModuleType("src.services.backend_client")
    backend_module.fetch_leadership_metrics = lambda **kwargs: (
        backend_calls.setdefault("kwargs", kwargs),
        {"total": 3},
    )[1]
    monkeypatch.setitem(sys.modules, "src.services.backend_client", backend_module)

    failures = []

    result = components_bridge_helpers.cached_get_leadership_metrics(
        [10, 20],
        7,
        actor_username="alice",
        backend_read_proxy_enabled_fn=lambda: True,
        handle_backend_read_failure_fn=lambda **kwargs: failures.append(kwargs),
    )

    assert result == {"total": 3}
    assert backend_calls["kwargs"]["cycle_id"] == 7
    assert backend_calls["kwargs"]["usernames"] == ["10", "20"]
    assert backend_calls["kwargs"]["actor_username"] == "alice"
    assert failures == []


def test_cached_get_leadership_metrics_falls_back_after_backend_error_payload(
    monkeypatch,
):
    backend_module = ModuleType("src.services.backend_client")
    backend_module.fetch_leadership_metrics = lambda **_kwargs: {"error": "unavailable"}
    monkeypatch.setitem(sys.modules, "src.services.backend_client", backend_module)

    crud_calls = {}
    crud_module = ModuleType("src.crud")
    crud_module.get_leadership_metrics = lambda user_ids, cycle_id: (
        crud_calls.setdefault("args", (user_ids, cycle_id)),
        {"fallback": True},
    )[1]
    monkeypatch.setitem(sys.modules, "src.crud", crud_module)

    failures = []

    result = components_bridge_helpers.cached_get_leadership_metrics(
        [10],
        5,
        actor_username="alice",
        backend_read_proxy_enabled_fn=lambda: True,
        handle_backend_read_failure_fn=lambda **kwargs: failures.append(kwargs),
    )

    assert result == {"fallback": True}
    assert failures and failures[0]["operation"] == "leadership metrics"
    assert failures[0]["backend_result"] == {"error": "unavailable"}
    assert crud_calls["args"] == ([10], 5)


def test_cached_get_leadership_metrics_reraises_runtime_error(monkeypatch):
    backend_module = ModuleType("src.services.backend_client")

    def _raise_runtime(**_kwargs):
        raise RuntimeError("boom")

    backend_module.fetch_leadership_metrics = _raise_runtime
    monkeypatch.setitem(sys.modules, "src.services.backend_client", backend_module)

    with pytest.raises(RuntimeError, match="boom"):
        components_bridge_helpers.cached_get_leadership_metrics(
            [1],
            1,
            actor_username="alice",
            backend_read_proxy_enabled_fn=lambda: True,
            handle_backend_read_failure_fn=lambda **_kwargs: None,
        )


def test_resolve_node_details_enforces_binding_sync_before_delegate():
    calls: list[str] = []

    def _ensure_bindings():
        calls.append("ensure")

    def _resolve(*_args, **_kwargs):
        calls.append("resolve")
        return {"ok": True}

    helper_module = SimpleNamespace(resolve_node_details=_resolve)

    result = components_bridge_helpers.resolve_node_details(
        "task_1",
        node_lookup={"task_1": {}},
        ensure_model_bindings_current_fn=_ensure_bindings,
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: None,
        parse_typed_ref_fn=lambda _raw: ("task", 1),
        get_session_context_fn=lambda: None,
        models_by_type={},
        logger=None,
        atlas_node_details_helpers_module=helper_module,
    )

    assert result == {"ok": True}
    assert calls == ["ensure", "resolve"]
