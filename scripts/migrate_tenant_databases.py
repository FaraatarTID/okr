"""Safely orchestrate Alembic migrations across provisioned tenant databases."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence
from urllib.request import urlopen

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.saas.control_plane import ControlPlane
from src.saas.provisioning import LocalDisposableEnvironmentProvider


@dataclass(frozen=True, slots=True)
class TenantTarget:
    environment_id: str
    database_resource_id: str


@dataclass(frozen=True, slots=True)
class TenantMigrationResult:
    environment_id: str
    database_resource_id: str
    revision: str | None
    success: bool
    duration_seconds: float
    attempts: int
    error: str | None = None
    expected_revision: str | None = None
    old_revision: str | None = None
    new_revision: str | None = None
    wave: int = 1
    started_at: str | None = None
    completed_at: str | None = None
    preflight: dict | None = None
    postflight: dict | None = None
    failure_classification: str | None = None


@dataclass
class MigrationReport:
    results: list[TenantMigrationResult] = field(default_factory=list)
    dry_run: bool = False
    release_id: str | None = None
    migration_artifact: str | None = None
    expected_revision: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    @property
    def succeeded(self):
        return [item for item in self.results if item.success]

    @property
    def failed(self):
        return [item for item in self.results if not item.success]

    @property
    def ok(self):
        return not self.failed

    def to_mapping(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "ok": self.ok,
            "release_id": self.release_id,
            "migration_artifact": self.migration_artifact,
            "expected_revision": self.expected_revision,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "succeeded": len(self.succeeded),
            "failed": len(self.failed),
            "results": [asdict(item) for item in self.results],
        }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _revision(value: str | None) -> str | None:
    return value.strip().split()[0] if value and value.strip() else None


def _repository_expected_head(timeout_seconds: float = 30) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("could not determine repository Alembic head")
    heads = [
        _revision(line)
        for line in completed.stdout.splitlines()
        if "(head)" in line.lower()
    ]
    heads = [head for head in heads if head]
    if len(heads) != 1:
        raise RuntimeError(
            f"repository must have exactly one Alembic head; found {len(heads)}"
        )
    return heads[0]


def _resolve_database_url(
    *, resource_id: str, url_resolver: Mapping[str, str] | Callable[[str], str] | None
) -> str | None:
    if url_resolver is None:
        return os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL")
    return (
        url_resolver(resource_id)
        if callable(url_resolver)
        else url_resolver.get(resource_id)
    )


def _alembic_current(
    database_url: str, timeout_seconds: float
) -> tuple[str | None, str | None]:
    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env={
            **os.environ,
            "OKR_DATABASE_URL": database_url,
            "DATABASE_URL": database_url,
        },
        check=False,
    )
    if current.returncode:
        return (
            None,
            f"alembic current failed: {(current.stderr or current.stdout or 'exit ' + str(current.returncode)).strip()}",
        )
    return _revision(
        current.stdout.splitlines()[-1] if current.stdout.splitlines() else None
    ), None


def _default_runner(
    *, database_url: str, timeout_seconds: float
) -> tuple[str | None, str | None]:
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env={
            **os.environ,
            "OKR_DATABASE_URL": database_url,
            "DATABASE_URL": database_url,
        },
        check=False,
    )
    if upgrade.returncode:
        return (
            None,
            f"alembic upgrade head failed: {(upgrade.stderr or upgrade.stdout or 'exit ' + str(upgrade.returncode)).strip()}",
        )
    return _alembic_current(database_url, timeout_seconds)


def _classify(error: str | None) -> str | None:
    if not error:
        return None
    text = error.lower()
    if "revision mismatch" in text or "expected-head" in text:
        return "revision_mismatch"
    if "incompatible schema" in text or "multiple heads" in text:
        return "incompatible_schema"
    if any(
        token in text
        for token in (
            "timeout",
            "temporar",
            "connection",
            "network",
            "unavailable",
            "reset",
        )
    ):
        return "transient_connectivity"
    return "permanent_failure"


def _http_probe(url: str, timeout_seconds: float) -> tuple[bool, str | None]:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - configured operator URL
            return 200 <= response.status < 400, f"HTTP {response.status}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def list_tenant_targets(
    *,
    provisioning_state_file: Path | None = None,
    control_plane_state_file: Path | None = None,
    tenants: Sequence[str] | None = None,
) -> list[TenantTarget]:
    if provisioning_state_file is None and control_plane_state_file is None:
        raise ValueError(
            "tenant inventory is required; provide --provisioning-state-file or --control-plane-state-file"
        )
    provider = (
        LocalDisposableEnvironmentProvider(provisioning_state_file)
        if provisioning_state_file
        else None
    )
    control_plane = (
        ControlPlane(state_path=control_plane_state_file)
        if control_plane_state_file
        else None
    )
    records: Iterable = (
        provider.environments.values()
        if provider
        else control_plane.list_environments()
    )
    wanted = set(tenants or ())
    return sorted(
        [
            TenantTarget(
                str(getattr(r, "environment_id")),
                str(
                    getattr(r, "database_resource_id", None)
                    or getattr(r, "database_target", None)
                ),
            )
            for r in records
            if getattr(r, "environment_id", None)
            and (
                getattr(r, "database_resource_id", None)
                or getattr(r, "database_target", None)
            )
            and (not wanted or getattr(r, "environment_id") in wanted)
        ],
        key=lambda t: t.environment_id,
    )


def migrate_tenants(
    targets: Sequence[TenantTarget],
    *,
    url_resolver=None,
    runner=None,
    timeout_seconds: float = 300.0,
    max_retries: int = 0,
    fail_fast: bool = False,
    dry_run: bool = False,
    expected_revision: str | None = None,
    canary_tenants: Sequence[str] = (),
    batch_size: int = 0,
    max_concurrency: int = 1,
    continue_on_wave_failure: bool = False,
    preflight=None,
    postflight=None,
    readiness_urls: Mapping[str, str] | None = None,
    health_probe_mode: str = "off",
    release_id: str | None = None,
    migration_artifact: str | None = None,
) -> MigrationReport:
    """Run ordered canary/batch waves. Retries are restricted to connectivity failures."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    if batch_size < 0 or max_retries < 0 or timeout_seconds <= 0:
        raise ValueError(
            "batch size/retries must be non-negative and timeout must be positive"
        )
    if health_probe_mode not in {"off", "optional", "required"}:
        raise ValueError("invalid health_probe_mode")
    expected = expected_revision or _repository_expected_head()
    ordered = sorted(targets, key=lambda t: t.environment_id)
    canaries = [t for t in ordered if t.environment_id in set(canary_tenants)]
    remaining = [t for t in ordered if t.environment_id not in set(canary_tenants)]
    waves = ([canaries] if canaries else []) + (
        [remaining[i : i + batch_size] for i in range(0, len(remaining), batch_size)]
        if batch_size
        else ([remaining] if remaining else [])
    )
    report = MigrationReport(
        dry_run=dry_run,
        release_id=release_id,
        migration_artifact=migration_artifact,
        expected_revision=expected,
        started_at=_now(),
    )
    execute = runner or (
        lambda target, url: _default_runner(
            database_url=url, timeout_seconds=timeout_seconds
        )
    )
    read_revision = preflight or (
        lambda target, url: _alembic_current(url, timeout_seconds)
    )

    def one(target: TenantTarget, wave: int) -> TenantMigrationResult:
        started_clock, started_at = time.monotonic(), _now()
        url = _resolve_database_url(
            resource_id=target.database_resource_id, url_resolver=url_resolver
        )

        def result(
            success, attempts=0, error=None, old=None, new=None, pre=None, post=None
        ):
            return TenantMigrationResult(
                target.environment_id,
                target.database_resource_id,
                new,
                success,
                time.monotonic() - started_clock,
                attempts,
                error,
                expected,
                old,
                new,
                wave,
                started_at,
                _now(),
                pre,
                post,
                _classify(error),
            )

        if dry_run:
            return result(True)
        if not url:
            return result(
                False,
                error=f"no database URL for resource {target.database_resource_id}",
            )
        old, error = read_revision(target, url)
        pre = {
            "ok": error is None,
            "revision": old,
            "expected_revision": expected,
            "matches_expected": old == expected,
            "detail": error,
        }
        if error:
            return result(False, error=f"preflight failed: {error}", old=old, pre=pre)
        if old is None:
            return result(
                False,
                error="preflight failed: tenant revision was not reported",
                old=old,
                pre=pre,
            )
        attempts = 0
        new = None
        while attempts <= max_retries:
            attempts += 1
            try:
                new, error = execute(target, url)
            except subprocess.TimeoutExpired:
                new, error = None, "migration timeout"
            except Exception as exc:
                new, error = None, str(exc)
            if error is None or _classify(error) != "transient_connectivity":
                break
        if error:
            return result(False, attempts, f"migration failed: {error}", old, new, pre)
        new = _revision(new)
        if new != expected:
            return result(
                False,
                attempts,
                f"expected-head check failed: revision mismatch (expected {expected}, got {new})",
                old,
                new,
                pre,
            )
        post = {"revision_ok": True}
        if postflight:
            ok, detail = postflight(target, url)
            post["custom_probe"] = {"ok": ok, "detail": detail}
            if not ok:
                return result(
                    False, attempts, f"postflight failed: {detail}", old, new, pre, post
                )
        readiness_url = (readiness_urls or {}).get(target.environment_id)
        if health_probe_mode != "off" and readiness_url:
            ok, detail = _http_probe(readiness_url, timeout_seconds)
            post["readiness"] = {"url": readiness_url, "ok": ok, "detail": detail}
            if not ok:
                return result(
                    False,
                    attempts,
                    f"postflight readiness failed: {detail}",
                    old,
                    new,
                    pre,
                    post,
                )
        elif health_probe_mode == "required":
            return result(
                False,
                attempts,
                "postflight failed: readiness URL is required",
                old,
                new,
                pre,
                post,
            )
        return result(True, attempts, old=old, new=new, pre=pre, post=post)

    halted = False
    for wave_number, wave in enumerate(waves, 1):
        if halted:
            report.results.extend(
                TenantMigrationResult(
                    t.environment_id,
                    t.database_resource_id,
                    None,
                    False,
                    0,
                    0,
                    "skipped after prior wave failure",
                    expected,
                    None,
                    None,
                    wave_number,
                    _now(),
                    _now(),
                    None,
                    None,
                    "skipped",
                )
                for t in wave
            )
            continue
        with ThreadPoolExecutor(max_workers=min(max_concurrency, len(wave))) as pool:
            completed = (
                list(as_completed({pool.submit(one, t, wave_number): t for t in wave}))
                if wave
                else []
            )
        report.results.extend(
            sorted(
                (future.result() for future in completed),
                key=lambda r: r.environment_id,
            )
        )
        if (
            any(not r.success for r in report.results if r.wave == wave_number)
            and not continue_on_wave_failure
        ):
            halted = True
        if fail_fast and halted:
            continue
    report.results.sort(key=lambda r: (r.wave, r.environment_id))
    report.completed_at = _now()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provisioning-state-file",
        type=Path,
        default=Path("tmp/saas-environments.json"),
    )
    parser.add_argument("--control-plane-state-file", type=Path)
    parser.add_argument("--tenant", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Bounded parallelism for each wave (default: sequential).",
    )
    parser.add_argument("--canary-tenant", action="append", default=[])
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--continue-on-wave-failure", action="store_true")
    parser.add_argument(
        "--health-probe-mode", choices=("off", "optional", "required"), default="off"
    )
    parser.add_argument("--readiness-urls-file", type=Path)
    parser.add_argument(
        "--expected-revision",
        help="Override only for a controlled recovery; normally repository head is used.",
    )
    parser.add_argument("--release-id", default=os.getenv("GITHUB_RUN_ID"))
    parser.add_argument("--migration-artifact", default=os.getenv("GITHUB_SHA"))
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-urls-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    resolver = (
        json.loads(args.database_urls_file.read_text())
        if args.database_urls_file
        else None
    )
    readiness = (
        json.loads(args.readiness_urls_file.read_text())
        if args.readiness_urls_file
        else None
    )
    if (
        args.dry_run
        and not args.provisioning_state_file.exists()
        and args.control_plane_state_file is None
    ):
        targets = []
    else:
        targets = list_tenant_targets(
            provisioning_state_file=args.provisioning_state_file
            if args.provisioning_state_file.exists()
            else None,
            control_plane_state_file=args.control_plane_state_file,
            tenants=args.tenant or None,
        )
    if len(targets) > 1 and args.database_urls_file is None:
        parser.error(
            "multiple tenants require --database-urls-file; refusing to reuse one database URL across tenants"
        )
    if (
        not args.dry_run
        and not targets
        and not args.provisioning_state_file.exists()
        and args.control_plane_state_file is None
    ):
        parser.error(
            "tenant inventory is required; provide --provisioning-state-file or --control-plane-state-file"
        )
    report = migrate_tenants(
        targets,
        url_resolver=resolver,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        fail_fast=args.fail_fast,
        dry_run=args.dry_run,
        expected_revision=args.expected_revision,
        canary_tenants=args.canary_tenant,
        batch_size=args.batch_size,
        max_concurrency=args.max_concurrency,
        continue_on_wave_failure=args.continue_on_wave_failure,
        readiness_urls=readiness,
        health_probe_mode=args.health_probe_mode,
        release_id=args.release_id,
        migration_artifact=args.migration_artifact,
    )
    payload = json.dumps(report.to_mapping(), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
