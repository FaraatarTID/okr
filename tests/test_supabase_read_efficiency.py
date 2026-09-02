from __future__ import annotations

from src.services import supabase_api_mode_transport as transport


def test_admin_scope_reuses_single_users_all_fetch(monkeypatch):
    import backend_app.scope_resolution as scope_resolution

    calls: list[str] = []
    users = [
        {"id": 7, "username": "admin", "role": "admin", "is_active": True},
        {"id": 8, "username": "member", "role": "member", "is_active": True},
    ]

    def fake_read(*, kind: str, params: dict, actor: str):
        calls.append(kind)
        if kind == "users.by_username":
            return {"user": users[0]}
        if kind == "users.all":
            return {"users": users}
        raise AssertionError(f"unexpected read kind: {kind}")

    monkeypatch.setattr(scope_resolution, "read_query_via_supabase_api", fake_read)

    scope = scope_resolution._resolve_actor_scope_via_supabase_api("admin")

    assert calls == ["users.all"]
    assert scope["owner_ids"] == {7, 8}
    assert scope["admin_ids"] == {7}


def test_admin_scope_can_resolve_actor_from_users_all(monkeypatch):
    import backend_app.scope_resolution as scope_resolution

    calls: list[str] = []
    users = [
        {"id": 7, "username": "admin", "role": "admin", "is_active": True},
        {"id": 8, "username": "member", "role": "member", "is_active": True},
    ]

    def fake_read(*, kind: str, params: dict, actor: str):
        calls.append(kind)
        if kind == "users.all":
            return {"users": users}
        raise AssertionError(f"unexpected read kind: {kind}")

    monkeypatch.setattr(scope_resolution, "read_query_via_supabase_api", fake_read)

    scope = scope_resolution._resolve_actor_scope_via_supabase_api("admin")

    assert calls == ["users.all"]
    assert scope["actor_id"] == 7
    assert scope["owner_ids"] == {7, 8}
    assert scope["admin_ids"] == {7}


def test_http_client_creation_is_serialized_and_reused(monkeypatch):
    import threading

    created: list[object] = []
    barrier = threading.Barrier(8)

    class FakeClient:
        def close(self):
            pass

    def fake_base_url():
        barrier.wait(timeout=2)
        return "https://example.supabase.co"

    def fake_client(*args, **kwargs):
        client = FakeClient()
        created.append(client)
        return client

    monkeypatch.setattr(transport, "_HTTP_CLIENT", None)
    monkeypatch.setattr(transport, "_HTTP_CLIENT_CONFIG", None)
    monkeypatch.setattr(transport, "_base_url", fake_base_url)
    monkeypatch.setattr(transport.httpx, "Client", fake_client)
    monkeypatch.setattr(transport, "_get_ssl_context", lambda: object())

    results: list[object] = []
    errors: list[BaseException] = []

    def load_client():
        try:
            results.append(transport._get_http_client())
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=load_client) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not errors
    assert len(created) == 1
    assert len({id(client) for client in results}) == 1
