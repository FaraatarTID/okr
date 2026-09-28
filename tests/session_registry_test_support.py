"""Real session-registry setup for actor-bound TestClient fixtures."""

from datetime import datetime, timezone
import hashlib


def registered_test_session_headers(*, actor_id: int = 1) -> dict[str, str]:
    """Return one real registered session binding without bypassing backend auth."""
    from backend_app.security_state import register_session

    session_id = f"test-session-registry-actor-binding-{actor_id:08d}"
    register_session(
        session_digest=hashlib.sha256(session_id.encode("ascii")).hexdigest(),
        actor_id=str(actor_id),
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    return {
        "X-OKR-Session-Id": session_id,
        "X-OKR-Session-Actor": str(actor_id),
    }


def attach_registered_test_session(client, *, actor_id: int = 1) -> None:
    """Attach a registered actor session to a client default header set."""
    client.headers.update(registered_test_session_headers(actor_id=actor_id))
