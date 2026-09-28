"""Shared cryptographic helpers for request signing."""

from __future__ import annotations

import hashlib


def body_digest_hex(body: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *body*."""
    return hashlib.sha256(body or b"").hexdigest()


def canonical_signing_payload(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_digest: str,
    session_id: str | None = None,
    session_actor: str | None = None,
) -> str:
    """Build the canonical payload string for HMAC request signing."""
    parts = [
        str(method or "").strip().upper(),
        str(path or "/").strip() or "/",
        str(timestamp or "").strip(),
        str(nonce or "").strip(),
        str(body_digest or "").strip(),
    ]
    if session_id is not None or session_actor is not None:
        # Encode both optional values in fixed, labeled slots whenever either is
        # present. Hex avoids newline/delimiter ambiguity for opaque identifiers.
        sid = str(session_id).encode("utf-8").hex() if session_id is not None else "-"
        actor = (
            str(session_actor).encode("utf-8").hex()
            if session_actor is not None
            else "-"
        )
        parts.extend([f"session_id:{sid}", f"session_actor:{actor}"])
    return "\n".join(parts)
