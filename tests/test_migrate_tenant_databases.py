from __future__ import annotations

from scripts.migrate_tenant_databases import (
    TenantTarget,
    _default_runner,
    list_tenant_targets,
    migrate_tenants,
)


def _target(environment_id: str) -> TenantTarget:
    return TenantTarget(
        environment_id=environment_id, database_resource_id=f"db:{environment_id}"
    )


def test_no_tenants_is_success_with_empty_report() -> None:
    report = migrate_tenants([], url_resolver={})
    assert report.ok
    assert report.results == []
    assert report.to_mapping()["ok"] is True


def test_single_and_multiple_tenants_record_revision_duration_and_error() -> None:
    calls: list[str] = []

    def runner(target: TenantTarget, url: str):
        calls.append(target.environment_id)
        return "drop_global_cycle_index (head)", None

    report = migrate_tenants(
        [_target("env-a"), _target("env-b")],
        url_resolver={"db:env-a": "sqlite:///a.db", "db:env-b": "sqlite:///b.db"},
        runner=runner,
    )
    assert report.ok
    assert calls == ["env-a", "env-b"]
    for result in report.results:
        assert result.revision == "drop_global_cycle_index (head)"
        assert result.duration_seconds >= 0
        assert result.attempts == 1
        assert result.error is None


def test_failed_tenant_marks_release_incomplete_and_rerun_is_safe() -> None:
    attempts = {"count": 0}

    def flaky(target: TenantTarget, url: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return None, "boom"
        return "head", None

    failing = migrate_tenants(
        [_target("env-a")],
        url_resolver={"db:env-a": "sqlite:///a.db"},
        runner=flaky,
        max_retries=0,
    )
    assert not failing.ok
    assert failing.failed[0].error == "boom"

    recovered = migrate_tenants(
        [_target("env-a")],
        url_resolver={"db:env-a": "sqlite:///a.db"},
        runner=lambda target, url: ("head", None),
    )
    assert recovered.ok


def test_partially_migrated_and_failed_tenant_with_fail_fast() -> None:
    def runner(target: TenantTarget, url: str):
        if target.environment_id == "env-bad":
            return None, "migration failed"
        return "head", None

    report = migrate_tenants(
        [_target("env-ok"), _target("env-bad"), _target("env-never")],
        url_resolver={"db:env-ok": "u", "db:env-bad": "u", "db:env-never": "u"},
        runner=runner,
        fail_fast=True,
    )
    assert not report.ok
    assert [item.environment_id for item in report.results] == ["env-ok", "env-bad"]


def test_dry_run_lists_targets_without_modifying() -> None:
    def runner(target: TenantTarget, url: str):  # pragma: no cover - must not run
        raise AssertionError("runner must not execute during dry run")

    report = migrate_tenants([_target("env-a")], runner=runner, dry_run=True)
    assert report.ok
    assert report.dry_run is True
    assert report.results[0].attempts == 0
    assert report.results[0].revision is None


def test_missing_database_url_is_reported_per_tenant() -> None:
    report = migrate_tenants([_target("env-a")], url_resolver={})
    assert not report.ok
    assert "no database URL" in (report.results[0].error or "")


def test_inventory_source_is_required() -> None:
    import pytest

    with pytest.raises(ValueError, match="tenant inventory is required"):
        list_tenant_targets()


def test_dry_run_without_inventory_uses_empty_report(monkeypatch, tmp_path) -> None:
    import scripts.migrate_tenant_databases as migration

    missing = tmp_path / "missing.json"
    monkeypatch.setattr(
        migration,
        "Path",
        lambda value: missing
        if value == "tmp/saas-environments.json"
        else __import__("pathlib").Path(value),
    )
    report = migration.migrate_tenants([], dry_run=True)
    assert report.ok is True
    assert report.results == []

    assert migration.main(["--dry-run"]) == 0


def test_current_revision_failure_is_reported(monkeypatch) -> None:
    from types import SimpleNamespace

    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=1, stdout="", stderr="database unavailable"),
        ]
    )
    monkeypatch.setattr(
        "scripts.migrate_tenant_databases.subprocess.run",
        lambda *args, **kwargs: next(responses),
    )

    revision, error = _default_runner(database_url="sqlite:///a.db", timeout_seconds=1)

    assert revision is None
    assert error == "alembic current failed: database unavailable"


def test_retry_succeeds_after_transient_failure() -> None:
    attempts = {"count": 0}

    def runner(target: TenantTarget, url: str):
        attempts["count"] += 1
        if attempts["count"] < 2:
            return None, "transient"
        return "head", None

    report = migrate_tenants(
        [_target("env-a")], url_resolver={"db:env-a": "u"}, runner=runner, max_retries=1
    )
    assert report.ok
    assert report.results[0].attempts == 2


def test_inventory_lists_provisioned_tenants(tmp_path) -> None:
    from src.saas.environment_contract import EnvironmentManifest
    from src.saas.operator_credentials import OperatorCredential
    from src.saas.provisioning import LocalDisposableEnvironmentProvider, Provisioner

    state_file = tmp_path / "envs.json"
    provider = LocalDisposableEnvironmentProvider(state_file)
    provisioner = Provisioner(provider, operator=OperatorCredential.for_test("op"))
    for env_id in ("env-a", "env-b"):
        provisioner.provision(
            EnvironmentManifest(
                environment_id=env_id,
                customer_id=f"customer-{env_id}",
                deployment_profile="single_tenant_saas",
                application_version="v1",
                database_target=f"db-resource:{env_id}",
            )
        )
    targets = list_tenant_targets(provisioning_state_file=state_file)
    assert [item.environment_id for item in targets] == ["env-a", "env-b"]
    filtered = list_tenant_targets(
        provisioning_state_file=state_file, tenants=["env-b"]
    )
    assert [item.environment_id for item in filtered] == ["env-b"]
