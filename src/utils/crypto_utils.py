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
) -> str:
    """Build the canonical payload string for HMAC request signing."""
    return "\n".join(
        [
            str(method or "").strip().upper(),
            str(path or "/").strip() or "/",
            str(timestamp or "").strip(),
            str(nonce or "").strip(),
            str(body_digest or "").strip(),
        ]
    )
