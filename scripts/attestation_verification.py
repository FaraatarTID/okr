"""Verify evidence attestation signatures against a configured key.

The defect this module exists to close: both evidence verifiers checked only that
`signed_payload_sha256` equalled a digest recomputed from the same file, plus a
signature length floor and an algorithm name. That is self-consistent by
construction, so a fabricated signature string passed. A signature is only evidence
if it is checked against key material the evidence author does not control.

Two families are supported:

* `provider-signed` is HMAC-SHA256 over the canonical payload, using the secret in
  `OKR_SAAS_ATTESTATION_SECRET`. This is the algorithm the repository actually uses.
* `ed25519` and `rsa-pss-sha256` are verified against a PEM public key supplied in
  `OKR_SAAS_ATTESTATION_PUBLIC_KEY_PEM` or read from the path in
  `OKR_SAAS_ATTESTATION_PUBLIC_KEY_PATH`.

Every path fails closed. A missing secret, a missing public key, an unsupported
algorithm, a malformed signature and a mismatched signature are all rejections, never
a warning, so an attestation cannot pass by being unverifiable.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HMAC_ALGORITHM = "provider-signed"
ED25519_ALGORITHM = "ed25519"
RSA_PSS_ALGORITHM = "rsa-pss-sha256"
ASYMMETRIC_ALGORITHMS = (ED25519_ALGORITHM, RSA_PSS_ALGORITHM)
SUPPORTED_ALGORITHMS = (HMAC_ALGORITHM, *ASYMMETRIC_ALGORITHMS)

ATTESTATION_SECRET_ENV = "OKR_SAAS_ATTESTATION_SECRET"
ATTESTATION_PUBLIC_KEY_ENV = "OKR_SAAS_ATTESTATION_PUBLIC_KEY_PEM"
ATTESTATION_PUBLIC_KEY_PATH_ENV = "OKR_SAAS_ATTESTATION_PUBLIC_KEY_PATH"

HMAC_SIGNATURE_PREFIX = "hmac-sha256:"


class AttestationError(ValueError):
    """Raised when an attestation signature cannot be verified."""


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Return the canonical byte form a signature must cover.

    Sorted keys and no whitespace, so signer and verifier cannot disagree about
    formatting. Both evidence verifiers and the Phase 1 evidence check use this, so
    there is one canonical form rather than one per script.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(payload: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(payload)).hexdigest()}"


def unsigned_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    """Return the evidence with its `attestation` member removed."""
    return {key: value for key, value in evidence.items() if key != "attestation"}


def sign_hmac(payload: dict[str, Any], secret: str) -> str:
    """Produce the signature an HMAC attestation must carry."""
    digest = hmac.new(secret.encode("utf-8"), canonical_bytes(payload), hashlib.sha256)
    return HMAC_SIGNATURE_PREFIX + digest.hexdigest()


def hmac_matches(payload: dict[str, Any], signature: str, secret: str) -> bool:
    """Constant-time comparison of a signature against the expected HMAC.

    Callers must not compare signatures with `==`, so the comparison lives here.
    """
    return hmac.compare_digest(signature, sign_hmac(payload, secret))


def _secret(secret: str | None) -> str:
    if secret is not None:
        return secret
    return os.environ.get(ATTESTATION_SECRET_ENV, "")


def attach_attestation(
    payload: dict[str, Any],
    *,
    provider: str,
    key_id: str,
    evidence_id: str,
    secret: str | None = None,
    issued_at: str | None = None,
) -> dict[str, Any]:
    """Return `payload` with a signed `attestation` member.

    Both `signed_payload_sha256` and `signature` cover the payload without its
    `attestation`, which is exactly what `verify_attestation_signature` recomputes, so a
    producer and a verifier cannot disagree about what was signed.

    This is the counterpart to verification, and it lives here so producers do not each
    reimplement the canonical form. A release manifest and a rollback record are both
    signed this way. Note that adding any member to an already-attested payload
    invalidates its signature, because the payload is what was signed - which is why a
    record derived from an attested manifest carries its own attestation rather than
    reusing the manifest's.
    """
    configured = _secret(secret)
    if not configured:
        raise AttestationError(
            f"{ATTESTATION_SECRET_ENV} must be configured to sign an attestation"
        )
    unsigned = unsigned_payload(payload)
    attestation = {
        "provider": provider,
        "evidence_id": evidence_id,
        "algorithm": HMAC_ALGORITHM,
        "key_id": key_id,
        "issued_at": issued_at or datetime.now(timezone.utc).isoformat(),
        "signed_payload_sha256": canonical_digest(unsigned),
        "signature": sign_hmac(unsigned, configured),
    }
    return {**unsigned, "attestation": attestation}


def _public_key_pem(public_key_pem: str | None) -> str:
    if public_key_pem is not None:
        return public_key_pem
    inline = os.environ.get(ATTESTATION_PUBLIC_KEY_ENV, "")
    if inline.strip():
        return inline
    path = os.environ.get(ATTESTATION_PUBLIC_KEY_PATH_ENV, "").strip()
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise AttestationError(
            f"{ATTESTATION_PUBLIC_KEY_PATH_ENV} could not be read: {exc}"
        ) from exc


def _decode_asymmetric_signature(signature: str, algorithm: str, label: str) -> bytes:
    prefix = f"{algorithm}:"
    if not signature.startswith(prefix):
        raise AttestationError(
            f"{label}.signature must carry the '{prefix}' prefix for algorithm {algorithm}"
        )
    try:
        return base64.b64decode(signature[len(prefix) :], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttestationError(
            f"{label}.signature must be base64 after the algorithm prefix"
        ) from exc


def _verify_asymmetric(
    message: bytes, signature: str, algorithm: str, public_key_pem: str, label: str
) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
    except ImportError as exc:  # pragma: no cover - declared dependency is present
        raise AttestationError(
            "asymmetric attestation verification requires the 'cryptography' package"
        ) from exc

    try:
        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise AttestationError(
            "the configured attestation public key is not a valid PEM public key"
        ) from exc

    raw = _decode_asymmetric_signature(signature, algorithm, label)
    try:
        if algorithm == ED25519_ALGORITHM:
            if not isinstance(key, ed25519.Ed25519PublicKey):
                raise AttestationError(
                    f"{label} public key is not an Ed25519 public key"
                )
            key.verify(raw, message)
        else:
            if not isinstance(key, rsa.RSAPublicKey):
                raise AttestationError(f"{label} public key is not an RSA public key")
            key.verify(
                raw,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH,
                ),
                hashes.SHA256(),
            )
    except InvalidSignature as exc:
        raise AttestationError(
            f"{label}.signature does not verify against the configured public key"
        ) from exc


def verify_attestation_signature(
    evidence: dict[str, Any],
    *,
    label: str = "attestation",
    secret: str | None = None,
    public_key_pem: str | None = None,
) -> str:
    """Verify the attestation on `evidence` and return the verified algorithm.

    Raises `AttestationError` on any rejection. The signed payload is the evidence
    without its `attestation` member, which is the same payload that
    `signed_payload_sha256` covers.
    """
    attestation = evidence.get("attestation")
    if not isinstance(attestation, dict):
        raise AttestationError(f"{label} must be an object")

    algorithm = str(attestation.get("algorithm", "")).strip().lower()
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise AttestationError(
            f"{label}.algorithm must be one of {', '.join(SUPPORTED_ALGORITHMS)}"
        )

    signature = str(attestation.get("signature", "")).strip()
    if not signature:
        raise AttestationError(f"{label}.signature must be a non-empty string")

    message = canonical_bytes(unsigned_payload(evidence))

    if algorithm == HMAC_ALGORITHM:
        configured = _secret(secret)
        if not configured:
            raise AttestationError(
                f"{label} is {HMAC_ALGORITHM} but {ATTESTATION_SECRET_ENV} is not "
                "configured, so the signature cannot be verified"
            )
        if not hmac_matches(unsigned_payload(evidence), signature, configured):
            raise AttestationError(
                f"{label}.signature does not verify against the configured secret"
            )
        return algorithm

    configured_key = _public_key_pem(public_key_pem)
    if not configured_key:
        raise AttestationError(
            f"{label} is {algorithm} but neither {ATTESTATION_PUBLIC_KEY_ENV} nor "
            f"{ATTESTATION_PUBLIC_KEY_PATH_ENV} is configured, so the signature "
            "cannot be verified"
        )
    _verify_asymmetric(message, signature, algorithm, configured_key, label)
    return algorithm
