"""Restore adapter selection must match provider validation."""

import pytest

from src.saas.backup_operations import (
    LocalBackupProvider,
    ProviderContractError,
    RestoreManager,
)
from src.saas.operator_credentials import OperatorCredential


class ProductionBackup(LocalBackupProvider):
    provider_name = "production"


class FalseyLocalRestore(LocalBackupProvider):
    def __bool__(self) -> bool:
        return False


def test_falsey_explicit_restore_provider_is_selected_and_validated() -> None:
    backup_provider = ProductionBackup()
    restore_provider = FalseyLocalRestore()
    credential = OperatorCredential.for_test("operator-a")

    manager = RestoreManager(
        backup_provider, restore_provider, operator=credential
    )
    assert manager.restore_provider is restore_provider

    with pytest.raises(ProviderContractError, match="production provider"):
        RestoreManager(
            backup_provider,
            restore_provider,
            operator=credential,
            production=True,
        )
