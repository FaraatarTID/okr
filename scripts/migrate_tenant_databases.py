"""Orchestrate Alembic migrations across provisioned tenant databases.

The orchestrator is provider-neutral: tenant inventory comes from the SaaS
control plane / provisioning state (opaque database resource identifiers),
while per-tenant execution is delegated to an injectable runner. The default
runner shells out to ``alembic upgrade head`` with a per-tenant database URL
supplied through the environment, so reruns stay idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

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


@dataclass
class MigrationReport:
    results: list[TenantMigrationResult] = field(default_factory=list)
    dry_run: bool = False

    @property
    def succeeded(self) -> list[TenantMigrationResult]:
        return [item for item in self.results if item.success]

    @property
    def failed(self) -> list[TenantMigrationResult]:
        return [item for item in self.results if not item.success]

    @property
    def ok(self) -> bool:
        return not self.failed

    def to_mapping(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "ok": self.ok,
            "succeeded": len(self.succeeded),
            "failed": len(self.failed),
            "results": [asdict(item) for item in self.results],
        }


def _resolve_database_url(*, resource_id: str, url_resolver: Mapping[str, str] | Callable[[str], str] | None) -> str | None:
    if url_resolver is None:
        return os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL")
    if callable(url_resolver):
        return url_resolver(resource_id)
    return url_resolver.get(resource_id)


def _default_runner(*, database_url: str, timeout_seconds: float) -> tuple[str | None, str | None]:
    """Run ``alembic upgrade head`` then report the current revision."""
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env={**os.environ, "OKR_DATABASE_URL": database_url, "DATABASE_URL": database_url},
        check=False,
    )
    if upgrade.returncode != 0:
        detail = (upgrade.stderr or upgrade.stdout or "").strip()
        return None, f"alembic upgrade head failed: {detail or 'exit ' + str(upgrade.returncode)}"
    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env={**os.environ, "OKR_DATABASE_URL": database_url, "DATABASE_URL": database_url},
        check=False,
    )
    if current.returncode != 0:
        detail = (current.stderr or current.stdout or "").strip()
        return None, f"alembic current failed: {detail or 'exit ' + str(current.returncode)}"
    revision = (current.stdout or "").strip().splitlines()
    head = revision[-1].strip() if revision else None
    return head or "head", None


def list_tenant_targets(
    *,
    provisioning_state_file: Path | None = None,
    control_plane_state_file: Path | None = None,
    tenants: Sequence[str] | None = None,
) -> list[TenantTarget]:
    """Authoritative tenant inventory: provisioned environments, optionally filtered."""
    if provisioning_state_file is None and control_plane_state_file is None:
        raise ValueError(
            "tenant inventory is required; provide --provisioning-state-file "
            "or --control-plane-state-file"
        )
    provider = LocalDisposableEnvironmentProvider(provisioning_state_file) if provisioning_state_file else None
    control_plane = ControlPlane(state_path=control_plane_state_file) if control_plane_state_file else None
    records: Iterable = ()
    if provider is not None:
        records = provider.environments.values()
    elif control_plane is not None:
        records = control_plane.list_environments()
    wanted = set(tenants or ())
    targets: list[TenantTarget] = []
    for record in records:
        environment_id = getattr(record, "environment_id", "")
        resource_id = getattr(record, "database_resource_id", None) or getattr(record, "database_target", None)
        if not environment_id or not resource_id:
            continue
        if wanted and environment_id not in wanted:
            continue
        targets.append(TenantTarget(environment_id=str(environment_id), database_resource_id=str(resource_id)))
    return sorted(targets, key=lambda item: item.environment_id)


def migrate_tenants(
    targets: Sequence[TenantTarget],
    *,
    url_resolver: Mapping[str, str] | Callable[[str], str] | None = None,
    runner: Callable[[TenantTarget, str], tuple[str | None, str | None]] | None = None,
    timeout_seconds: float = 300.0,
    max_retries: int = 0,
    fail_fast: bool = False,
    dry_run: bool = False,
) -> MigrationReport:
    """Migrate every target; idempotent reruns are safe (alembic upgrade head)."""
    report = MigrationReport(dry_run=dry_run)
    execute = runner or (lambda target, url: _default_runner(database_url=url, timeout_seconds=timeout_seconds))
    for target in targets:
        started = time.monotonic()
        if dry_run:
            report.results.append(
                TenantMigrationResult(
                    environment_id=target.environment_id,
                    database_resource_id=target.database_resource_id,
                    revision=None,
                    success=True,
                    duration_seconds=0.0,
                    attempts=0,
                )
            )
            continue
        database_url = _resolve_database_url(resource_id=target.database_resource_id, url_resolver=url_resolver)
        if not database_url:
            report.results.append(
                TenantMigrationResult(
                    environment_id=target.environment_id,
                    database_resource_id=target.database_resource_id,
                    revision=None,
                    success=False,
                    duration_seconds=time.monotonic() - started,
                    attempts=0,
                    error=f"no database URL for resource {target.database_resource_id}",
                )
            )
            if fail_fast:
                break
            continue
        revision: str | None = None
        error: str | None = None
        attempts = 0
        for attempt in range(max_retries + 1):
            attempts = attempt + 1
            try:
                revision, error = execute(target, database_url)
            except Exception as exc:  # noqa: BLE001 - record per-tenant failure
                revision, error = None, str(exc)
            if error is None:
                break
        report.results.append(
            TenantMigrationResult(
                environment_id=target.environment_id,
                database_resource_id=target.database_resource_id,
                revision=revision,
                success=error is None,
                duration_seconds=time.monotonic() - started,
                attempts=attempts,
                error=error,
            )
        )
        if error is not None and fail_fast:
            break
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provisioning-state-file", type=Path, default=Path("tmp/saas-environments.json"))
    parser.add_argument("--control-plane-state-file", type=Path, default=None)
    parser.add_argument("--tenant", action="append", default=[], help="Limit to these environment IDs (repeatable).")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first tenant failure.")
    parser.add_argument("--dry-run", action="store_true", help="List targets without modifying databases.")
    parser.add_argument("--database-urls-file", type=Path, default=None, help="JSON mapping of database resource ID to database URL.")
    parser.add_argument("--output", type=Path, default=None, help="Write the JSON report to this path.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    url_resolver: dict[str, str] | None = None
    if args.database_urls_file is not None:
        url_resolver = json.loads(args.database_urls_file.read_text(encoding="utf-8"))

    if args.dry_run and not args.provisioning_state_file.exists() and args.control_plane_state_file is None:
        targets: list[TenantTarget] = []
    else:
        targets = list_tenant_targets(
            provisioning_state_file=args.provisioning_state_file if args.provisioning_state_file.exists() else None,
            control_plane_state_file=args.control_plane_state_file,
            tenants=args.tenant or None,
        )
    if len(targets) > 1 and args.database_urls_file is None:
        parser.error(
            "multiple tenants require --database-urls-file; refusing to reuse "
            "one database URL across tenants"
        )
    if not args.dry_run and not targets and not args.provisioning_state_file.exists() and args.control_plane_state_file is None:
        parser.error("tenant inventory is required; provide --provisioning-state-file or --control-plane-state-file")
    report = migrate_tenants(
        targets,
        url_resolver=url_resolver,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        fail_fast=args.fail_fast,
        dry_run=args.dry_run,
    )
    payload = json.dumps(report.to_mapping(), indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
