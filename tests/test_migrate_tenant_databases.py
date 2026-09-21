from __future__ import annotations
import json
from scripts.migrate_tenant_databases import (
    TenantTarget,
    list_tenant_targets,
    migrate_tenants,
)


def _target(name):
    return TenantTarget(name, f"db:{name}")


def _urls(*names):
    return {f"db:{name}": "sqlite:///x" for name in names}


def _pre(target, url):
    return "old", None


def _runner(target, url):
    return "expected", None


def test_no_tenants_is_success_with_empty_report():
    assert migrate_tenants([], expected_revision="expected").ok


def test_canary_failure_halts_later_waves_and_records_skips():
    report = migrate_tenants(
        [_target("canary"), _target("later")],
        url_resolver=_urls("canary", "later"),
        expected_revision="expected",
        canary_tenants=["canary"],
        batch_size=1,
        preflight=_pre,
        runner=lambda t, u: (None, "connection unavailable")
        if t.environment_id == "canary"
        else _runner(t, u),
    )
    assert [r.environment_id for r in report.results] == ["canary", "later"]
    assert report.results[1].failure_classification == "skipped"


def test_postflight_failure_marks_tenant_failed():
    report = migrate_tenants(
        [_target("a")],
        url_resolver=_urls("a"),
        expected_revision="expected",
        preflight=_pre,
        runner=_runner,
        postflight=lambda t, u: (False, "BFF unhealthy"),
    )
    assert not report.ok and "postflight failed" in report.results[0].error


def test_mismatched_revision_is_not_retryable():
    calls = []

    def runner(t, u):
        calls.append(t.environment_id)
        return "wrong", None

    result = migrate_tenants(
        [_target("a")],
        url_resolver=_urls("a"),
        expected_revision="expected",
        preflight=_pre,
        runner=runner,
        max_retries=3,
    ).results[0]
    assert (
        result.failure_classification == "revision_mismatch"
        and result.attempts == 1
        and len(calls) == 1
    )


def test_retry_only_transient_failures():
    calls = []

    def flaky(t, u):
        calls.append(1)
        return (None, "connection reset") if len(calls) == 1 else ("expected", None)

    ok = migrate_tenants(
        [_target("a")],
        url_resolver=_urls("a"),
        expected_revision="expected",
        preflight=_pre,
        runner=flaky,
        max_retries=2,
    ).results[0]
    assert ok.success and ok.attempts == 2
    bad = migrate_tenants(
        [_target("b")],
        url_resolver=_urls("b"),
        expected_revision="expected",
        preflight=_pre,
        runner=lambda t, u: (None, "incompatible schema state"),
        max_retries=2,
    ).results[0]
    assert bad.attempts == 1 and bad.failure_classification == "incompatible_schema"


def test_parallel_completion_has_stable_report_order():
    report = migrate_tenants(
        [_target("z"), _target("a"), _target("m")],
        url_resolver=_urls("z", "a", "m"),
        expected_revision="expected",
        preflight=_pre,
        runner=_runner,
        max_concurrency=3,
    )
    assert [r.environment_id for r in report.results] == ["a", "m", "z"]


def test_report_serialization_contains_audit_fields():
    payload = migrate_tenants(
        [_target("a")],
        url_resolver=_urls("a"),
        expected_revision="expected",
        preflight=_pre,
        runner=_runner,
        release_id="release-1",
        migration_artifact="sha",
    ).to_mapping()
    assert json.loads(json.dumps(payload))["results"][0]["new_revision"] == "expected"
    assert {
        "release_id",
        "migration_artifact",
        "started_at",
        "completed_at",
    } <= payload.keys()


def test_inventory_source_is_required():
    import pytest

    with pytest.raises(ValueError):
        list_tenant_targets()
