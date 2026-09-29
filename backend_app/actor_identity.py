"""Actor identity resolution shared by the security dependency and scope resolution.

A leaf module: it imports nothing from `backend_app`, so both `security` and
`scope_resolution` can depend on it without an import cycle.
"""

from __future__ import annotations

from fastapi import HTTPException


def resolve_actor_username(
    *,
    header_actor: str | None,
    payload_actor: str | None,
) -> str:
    header = str(header_actor or "").strip()
    payload = str(payload_actor or "").strip()

    if header and payload and header != payload:
        raise HTTPException(
            status_code=403,
            detail="Actor mismatch: header and payload actors differ. Use the session actor.",
        )

    actor = header or payload
    if not actor:
        raise HTTPException(status_code=400, detail="Actor username is required.")
    if len(actor) > 128:
        raise HTTPException(status_code=400, detail="Actor username is too long.")
    return actor
