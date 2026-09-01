"""Authenticated operator credential resolution for lifecycle CLIs."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Mapping


class OperatorCredentialError(ValueError):
    """Raised when an operator token cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class OperatorCredential:
    """Authenticated operator identity passed across lifecycle service boundaries."""

    principal: str
    credential_id: str
    token_digest: str

    def __post_init__(self) -> None:
        if not self.principal.strip() or self.principal.upper() == "UNASSIGNED":
            raise ValueError("operator credential principal is invalid")
        if not self.credential_id.strip() or not self.token_digest.strip():
            raise ValueError("operator credential provenance is required")

    @classmethod
    def for_test(cls, principal: str) -> "OperatorCredential":
        return cls(principal, f"test:{principal}", "test-token-digest")


def resolve_operator_principal(*, token: str | None = None, credential_file: str | Path | None = None, environ: Mapping[str, str] | None = None) -> OperatorCredential:
    env = environ or os.environ
    supplied_token = token or env.get("OKR_OPERATOR_TOKEN", "")
    path = credential_file or env.get("OKR_OPERATOR_CREDENTIAL_FILE", "")
    if not supplied_token.strip():
        raise OperatorCredentialError("authenticated operator token is required")
    if not str(path).strip():
        raise OperatorCredentialError("operator credential file is required")
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OperatorCredentialError("operator credential file is invalid") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("operators"), list):
        raise OperatorCredentialError("operator credential file is invalid")
    token_hash = hashlib.sha256(supplied_token.encode("utf-8")).hexdigest()
    for entry in payload["operators"]:
        if not isinstance(entry, dict):
            continue
        if hmac.compare_digest(token_hash, str(entry.get("token_sha256", "")).lower()):
            principal = str(entry.get("principal", "")).strip()
            if not principal or principal.upper() == "UNASSIGNED":
                raise OperatorCredentialError("authenticated operator principal is invalid")
            credential_id = str(entry.get("credential_id", entry.get("principal", ""))).strip()
            return OperatorCredential(principal, credential_id, token_hash)
    raise OperatorCredentialError("invalid operator credential")
