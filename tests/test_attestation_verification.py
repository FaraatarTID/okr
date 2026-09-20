"""Tests for the shared attestation signature verifier.

Every signature here is produced independently of the module under test, using the
standard library for HMAC and `cryptography` directly for the asymmetric algorithms,
so a passing test means the verifier agreed with an outside signer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from scripts.attestation_verification import (
    ATTESTATION_PUBLIC_KEY_ENV,
    ATTESTATION_SECRET_ENV,
    AttestationError,
    verify_attestation_signature,
)


SECRET = "shared-attestation-test-secret"


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _evidence(algorithm: str, signature: str) -> dict[str, object]:
    evidence: dict[str, object] = {
        "schema_version": 1,
        "environment_id": "env-a",
        "status": "PASSED",
    }
    evidence["attestation"] = {
        "provider": "provider-a",
        "evidence_id": "provider-run-001",
        "algorithm": algorithm,
        "key_id": "key-2026",
        "signature": signature,
        "issued_at": "2026-09-01T10:00:00+00:00",
    }
    return evidence


def _unsigned(evidence: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in evidence.items() if key != "attestation"}


def _hmac_signature(payload: dict[str, object], secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), _canonical(payload), hashlib.sha256)
    return "hmac-sha256:" + digest.hexdigest()


def _ed25519_pair() -> tuple[ed25519.Ed25519PrivateKey, str]:
    key = ed25519.Ed25519PrivateKey.generate()
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return key, pem


def _rsa_pair() -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return key, pem


def _ed25519_signature(
    key: ed25519.Ed25519PrivateKey, payload: dict[str, object]
) -> str:
    return "ed25519:" + base64.b64encode(key.sign(_canonical(payload))).decode("ascii")


def _rsa_signature(key: rsa.RSAPrivateKey, payload: dict[str, object]) -> str:
    raw = key.sign(
        _canonical(payload),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256(),
    )
    return "rsa-pss-sha256:" + base64.b64encode(raw).decode("ascii")


def test_verifies_provider_signed_attestation_against_the_configured_secret() -> None:
    evidence = _evidence("provider-signed", "")
    evidence["attestation"]["signature"] = _hmac_signature(_unsigned(evidence))

    assert verify_attestation_signature(evidence, secret=SECRET) == "provider-signed"


def test_reads_the_secret_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ATTESTATION_SECRET_ENV, SECRET)
    evidence = _evidence("provider-signed", "")
    evidence["attestation"]["signature"] = _hmac_signature(_unsigned(evidence))

    assert verify_attestation_signature(evidence) == "provider-signed"


def test_rejects_attestation_signed_with_a_different_secret() -> None:
    evidence = _evidence("provider-signed", "")
    evidence["attestation"]["signature"] = _hmac_signature(
        _unsigned(evidence), "a-different-secret"
    )

    with pytest.raises(AttestationError, match="does not verify"):
        verify_attestation_signature(evidence, secret=SECRET)


def test_rejects_attestation_when_no_secret_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ATTESTATION_SECRET_ENV, raising=False)
    evidence = _evidence("provider-signed", "")
    evidence["attestation"]["signature"] = _hmac_signature(_unsigned(evidence))

    with pytest.raises(AttestationError, match="cannot be verified"):
        verify_attestation_signature(evidence)


def test_rejects_attestation_when_the_payload_changed_after_signing() -> None:
    evidence = _evidence("provider-signed", "")
    evidence["attestation"]["signature"] = _hmac_signature(_unsigned(evidence))
    evidence["environment_id"] = "env-b"

    with pytest.raises(AttestationError, match="does not verify"):
        verify_attestation_signature(evidence, secret=SECRET)


def test_verifies_ed25519_attestation_against_a_configured_public_key() -> None:
    key, pem = _ed25519_pair()
    evidence = _evidence("ed25519", "")
    evidence["attestation"]["signature"] = _ed25519_signature(key, _unsigned(evidence))

    assert verify_attestation_signature(evidence, public_key_pem=pem) == "ed25519"


def test_reads_the_public_key_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key, pem = _ed25519_pair()
    monkeypatch.setenv(ATTESTATION_PUBLIC_KEY_ENV, pem)
    evidence = _evidence("ed25519", "")
    evidence["attestation"]["signature"] = _ed25519_signature(key, _unsigned(evidence))

    assert verify_attestation_signature(evidence) == "ed25519"


def test_rejects_ed25519_attestation_signed_by_a_different_key() -> None:
    _, pem = _ed25519_pair()
    other, _ = _ed25519_pair()
    evidence = _evidence("ed25519", "")
    evidence["attestation"]["signature"] = _ed25519_signature(
        other, _unsigned(evidence)
    )

    with pytest.raises(AttestationError, match="does not verify"):
        verify_attestation_signature(evidence, public_key_pem=pem)


def test_rejects_ed25519_attestation_when_the_payload_changed_after_signing() -> None:
    key, pem = _ed25519_pair()
    evidence = _evidence("ed25519", "")
    evidence["attestation"]["signature"] = _ed25519_signature(key, _unsigned(evidence))
    evidence["status"] = "FAILED"

    with pytest.raises(AttestationError, match="does not verify"):
        verify_attestation_signature(evidence, public_key_pem=pem)


def test_rejects_asymmetric_attestation_when_no_public_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ATTESTATION_PUBLIC_KEY_ENV, raising=False)
    monkeypatch.delenv("OKR_SAAS_ATTESTATION_PUBLIC_KEY_PATH", raising=False)
    key, _ = _ed25519_pair()
    evidence = _evidence("ed25519", "")
    evidence["attestation"]["signature"] = _ed25519_signature(key, _unsigned(evidence))

    with pytest.raises(AttestationError, match="cannot be verified"):
        verify_attestation_signature(evidence)


def test_verifies_rsa_pss_attestation_against_a_configured_public_key() -> None:
    key, pem = _rsa_pair()
    evidence = _evidence("rsa-pss-sha256", "")
    evidence["attestation"]["signature"] = _rsa_signature(key, _unsigned(evidence))

    assert (
        verify_attestation_signature(evidence, public_key_pem=pem) == "rsa-pss-sha256"
    )


def test_rejects_ed25519_attestation_presented_with_an_rsa_key() -> None:
    ed_key, _ = _ed25519_pair()
    _, rsa_pem = _rsa_pair()
    evidence = _evidence("ed25519", "")
    evidence["attestation"]["signature"] = _ed25519_signature(
        ed_key, _unsigned(evidence)
    )

    with pytest.raises(AttestationError, match="not an Ed25519 public key"):
        verify_attestation_signature(evidence, public_key_pem=rsa_pem)


def test_rejects_unsupported_algorithm() -> None:
    evidence = _evidence("md5", "whatever")

    with pytest.raises(AttestationError, match="algorithm must be one of"):
        verify_attestation_signature(evidence, secret=SECRET)


def test_rejects_asymmetric_signature_without_the_algorithm_prefix() -> None:
    key, pem = _ed25519_pair()
    evidence = _evidence("ed25519", "")
    raw = base64.b64encode(key.sign(_canonical(_unsigned(evidence)))).decode("ascii")
    evidence["attestation"]["signature"] = raw

    with pytest.raises(AttestationError, match="prefix"):
        verify_attestation_signature(evidence, public_key_pem=pem)


def test_rejects_asymmetric_signature_that_is_not_base64() -> None:
    _, pem = _ed25519_pair()
    evidence = _evidence("ed25519", "ed25519:not-base64!!")

    with pytest.raises(AttestationError, match="base64"):
        verify_attestation_signature(evidence, public_key_pem=pem)


def test_rejects_empty_signature() -> None:
    evidence = _evidence("provider-signed", "")

    with pytest.raises(AttestationError, match="non-empty string"):
        verify_attestation_signature(evidence, secret=SECRET)


def test_rejects_missing_attestation() -> None:
    with pytest.raises(AttestationError, match="must be an object"):
        verify_attestation_signature({"schema_version": 1}, secret=SECRET)
