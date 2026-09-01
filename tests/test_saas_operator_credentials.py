from __future__ import annotations

import hashlib
import json

import pytest

from src.saas.operator_credentials import OperatorCredentialError, resolve_operator_principal


def _credential_file(tmp_path, token: str = "token-a"):
    path = tmp_path / "operators.json"
    path.write_text(
        json.dumps({
            "operators": [{
                "principal": "operator-a",
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            }]
        }),
        encoding="utf-8",
    )
    return path


def test_resolves_principal_from_environment_token_and_credential_file(tmp_path, monkeypatch):
    path = _credential_file(tmp_path)
    monkeypatch.setenv("OKR_OPERATOR_TOKEN", "token-a")
    assert resolve_operator_principal(credential_file=path).principal == "operator-a"


def test_rejects_missing_or_invalid_operator_credential(tmp_path, monkeypatch):
    path = _credential_file(tmp_path)
    monkeypatch.delenv("OKR_OPERATOR_TOKEN", raising=False)
    with pytest.raises(OperatorCredentialError, match="token"):
        resolve_operator_principal(credential_file=path)
    monkeypatch.setenv("OKR_OPERATOR_TOKEN", "wrong")
    with pytest.raises(OperatorCredentialError, match="invalid"):
        resolve_operator_principal(credential_file=path)


def test_rejects_unassigned_credential_principal(tmp_path, monkeypatch):
    path = tmp_path / "operators.json"
    token = "token-a"
    path.write_text(json.dumps({"operators": [{
        "principal": "UNASSIGNED",
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
    }]}), encoding="utf-8")
    monkeypatch.setenv("OKR_OPERATOR_TOKEN", token)
    with pytest.raises(OperatorCredentialError, match="principal"):
        resolve_operator_principal(credential_file=path)
