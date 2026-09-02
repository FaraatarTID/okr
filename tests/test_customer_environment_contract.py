import pytest
from pydantic import ValidationError

from src.saas.environment_contract import (
    BackupPolicy,
    EnvironmentEvent,
    EnvironmentManifest,
    EnvironmentState,
    transition,
)


def test_manifest_requires_isolated_database_target():
    manifest = EnvironmentManifest(
        environment_id="env-a",
        customer_id="customer-a",
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        database_target="db-resource:customer-a",
    )

    assert manifest.is_isolated is True


def test_single_tenant_manifest_rejects_missing_database_target():
    with pytest.raises(ValidationError, match="dedicated database target"):
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
        )


@pytest.mark.parametrize("field", ["environment_id", "customer_id", "application_version"])
def test_manifest_rejects_empty_identity_or_version(field):
    values = {
        "environment_id": "env-a",
        "customer_id": "customer-a",
        "deployment_profile": "single_tenant_saas",
        "application_version": "release-1",
        "database_target": "db-resource:customer-a",
    }
    values[field] = "   "

    with pytest.raises(ValidationError, match="non-empty text"):
        EnvironmentManifest(**values)


def test_manifest_rejects_unsupported_profile():
    with pytest.raises(ValidationError):
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="shared_database",
            application_version="release-1",
            database_target="db-resource:customer-a",
        )


def test_manifest_rejects_unsupported_contract_version():
    with pytest.raises(ValidationError):
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
            database_target="db-resource:customer-a",
            contract_version="v2",
        )


def test_manifest_rejects_invalid_lifecycle_state():
    with pytest.raises(ValidationError):
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
            database_target="db-resource:customer-a",
            lifecycle_state="ACTIVE",
        )


def test_event_rejects_invalid_lifecycle_event():
    with pytest.raises(ValueError):
        EnvironmentEvent("ACTIVATE_NOW")


def test_on_premise_manifest_rejects_control_plane_ownership():
    with pytest.raises(ValidationError, match="control-plane ownership"):
        EnvironmentManifest(
            environment_id="local",
            customer_id="local-owner",
            deployment_profile="on_premise",
            application_version="release-1",
            control_plane_owner="platform",
        )


@pytest.mark.parametrize("field", ["idempotency_key", "control_plane_owner"])
def test_manifest_rejects_empty_operational_metadata(field):
    with pytest.raises(ValidationError, match="non-empty"):
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
            database_target="db-resource:customer-a",
            **{field: "   "},
        )


@pytest.mark.parametrize("field", ["provider", "schedule"])
def test_backup_policy_rejects_empty_operational_metadata(field):
    with pytest.raises(ValidationError, match="non-empty"):
        BackupPolicy(**{field: "   "})


def test_retired_environment_cannot_return_to_ready():
    assert transition(EnvironmentState.RETIRED, EnvironmentEvent.ACTIVATE) is None


def test_legal_lifecycle_transition_is_explicit():
    assert (
        transition(
            EnvironmentState.PROVISIONING,
            EnvironmentEvent.COMPLETE_PROVISIONING,
        )
        is EnvironmentState.READY
    )


@pytest.mark.parametrize(
    ("state", "event", "expected"),
    [
        (EnvironmentState.READY, EnvironmentEvent.SUSPEND, EnvironmentState.SUSPENDED),
        (EnvironmentState.SUSPENDED, EnvironmentEvent.ACTIVATE, EnvironmentState.READY),
        (EnvironmentState.READY, EnvironmentEvent.BEGIN_UPGRADE, EnvironmentState.UPGRADING),
        (EnvironmentState.UPGRADING, EnvironmentEvent.COMPLETE_UPGRADE, EnvironmentState.READY),
        (EnvironmentState.DEGRADED, EnvironmentEvent.RECOVER, EnvironmentState.READY),
        (EnvironmentState.READY, EnvironmentEvent.RETIRE, EnvironmentState.RETIRED),
    ],
)
def test_representative_legal_lifecycle_transitions(state, event, expected):
    assert transition(state, event) is expected
