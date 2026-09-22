"""Durable, metadata-only fleet rollout state for isolated SaaS tenants.

This module deliberately stores opaque provider IDs and sanitized evidence only.
Customer database URLs remain in the secret provider and are resolved by a
migration runner immediately before use.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import hmac
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from src.saas.release_operations import ReleaseArtifact


class MigrationState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"


class RolloutPhase(StrEnum):
    CANARY = "canary"
    FLEET = "fleet"


class RolloutState(StrEnum):
    CANARY = "canary"
    RUNNING = "running"
    HALTED = "halted"
    COMPLETE = "complete"
    PAUSED = "paused"


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    version: str
    digest: str
    minimum_schema_revision: str
    maximum_schema_revision: str
    migration_phase: str = "expand"
    cleanup_approved: bool = False

    def __post_init__(self) -> None:
        if self.migration_phase not in {"expand", "contract"}:
            raise ValueError("migration_phase must be expand or contract")
        if self.migration_phase == "contract" and not self.cleanup_approved:
            raise ValueError(
                "contract migrations require explicit approved cleanup-release evidence"
            )
        if not self.digest.startswith("sha256:"):
            raise ValueError("release digest must be immutable sha256 identity")


metadata = MetaData()
tenants = Table(
    "saas_tenants",
    metadata,
    Column("environment_id", String(128), primary_key=True),
    Column("customer_id", String(128), unique=True, nullable=False),
    Column("database_resource_id", String(128), unique=True, nullable=False),
    Column("application_resource_id", String(128), unique=True),
    Column("state", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
rollouts = Table(
    "saas_rollouts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("release_json", Text, nullable=False),
    Column("state", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
migration_tasks = Table(
    "saas_migration_tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("rollout_id", Integer, nullable=False),
    Column("environment_id", String(128), nullable=False),
    Column("phase", String(32), nullable=False),
    Column("state", String(32), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("lease_owner", String(128)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("revision", String(256)),
    Column("error", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
audit_events = Table(
    "saas_operator_audit",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("environment_id", String(128), nullable=False),
    Column("event", String(64), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("evidence_json", Text, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
)
application_rollouts = Table(
    "saas_application_rollouts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("migration_rollout_id", Integer, nullable=False),
    Column("release_json", Text, nullable=False),
    Column("state", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
application_tasks = Table(
    "saas_application_tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("application_rollout_id", Integer, nullable=False),
    Column("environment_id", String(128), nullable=False),
    Column("phase", String(32), nullable=False),
    Column("state", String(32), nullable=False),
    Column("lease_owner", String(128)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("previous_digest", String(128)),
    Column("health_state", String(32)),
    Column("recovery_state", String(32)),
    Column("error", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _opaque(value: str) -> str:
    value = str(value or "").strip()
    if not value or any(token in value for token in ("://", "@", "?", "#")):
        raise ValueError("provider metadata must be a non-empty opaque resource ID")
    return value


class SqlControlPlane:
    """PostgreSQL/SQLAlchemy repository with transactional task leasing."""

    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, future=True)

    def create_schema(self) -> None:
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(
                    text(
                        """
                        CREATE OR REPLACE FUNCTION prevent_saas_operator_audit_mutation()
                        RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                          RAISE EXCEPTION 'saas_operator_audit is append-only';
                        END;
                        $$;
                        DROP TRIGGER IF EXISTS saas_operator_audit_append_only
                          ON saas_operator_audit;
                        CREATE TRIGGER saas_operator_audit_append_only
                        BEFORE UPDATE OR DELETE ON saas_operator_audit
                        FOR EACH ROW EXECUTE FUNCTION prevent_saas_operator_audit_mutation();
                        """
                    )
                )
            elif conn.dialect.name == "sqlite":
                conn.execute(
                    text(
                        """
                        CREATE TRIGGER IF NOT EXISTS saas_operator_audit_no_update
                        BEFORE UPDATE ON saas_operator_audit
                        BEGIN SELECT RAISE(ABORT, 'saas_operator_audit is append-only'); END;
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TRIGGER IF NOT EXISTS saas_operator_audit_no_delete
                        BEFORE DELETE ON saas_operator_audit
                        BEGIN SELECT RAISE(ABORT, 'saas_operator_audit is append-only'); END;
                        """
                    )
                )

    def register_tenant(
        self,
        environment_id: str,
        customer_id: str,
        database_resource_id: str,
        *,
        application_resource_id: str | None = None,
    ) -> None:
        values = {
            "environment_id": _opaque(environment_id),
            "customer_id": _opaque(customer_id),
            "database_resource_id": _opaque(database_resource_id),
            "application_resource_id": (
                _opaque(application_resource_id)
                if application_resource_id is not None
                else None
            ),
            "state": "ready",
            "created_at": _now(),
        }
        try:
            with self.engine.begin() as conn:
                conn.execute(tenants.insert().values(**values))
        except IntegrityError as exc:
            raise ValueError(
                "tenant environment, customer, or database resource is already registered"
            ) from exc

    def register_ready_tenant(
        self,
        environment_id: str,
        customer_id: str,
        database_resource_id: str,
        application_resource_id: str,
        *,
        actor: str,
        evidence: dict[str, Any],
    ) -> None:
        """Atomically make a verified tenant visible and preserve its evidence."""
        values = {
            "environment_id": _opaque(environment_id),
            "customer_id": _opaque(customer_id),
            "database_resource_id": _opaque(database_resource_id),
            "application_resource_id": _opaque(application_resource_id),
            "state": "ready",
            "created_at": _now(),
        }
        try:
            with self.engine.begin() as conn:
                conn.execute(tenants.insert().values(**values))
                conn.execute(
                    audit_events.insert().values(
                        environment_id=values["environment_id"],
                        event="PROVISION_READY",
                        actor=_opaque(actor),
                        evidence_json=json.dumps(evidence, sort_keys=True),
                        recorded_at=_now(),
                    )
                )
        except IntegrityError as exc:
            raise ValueError(
                "tenant environment, customer, database, or application resource is already registered"
            ) from exc

    def create_rollout(
        self,
        release: ReleaseMetadata,
        environment_ids: list[str],
        *,
        canary_count: int = 1,
    ) -> int:
        if canary_count < 1:
            raise ValueError("canary_count must be at least one")
        with self.engine.begin() as conn:
            known = set(
                conn.execute(
                    select(tenants.c.environment_id).where(
                        tenants.c.environment_id.in_(environment_ids)
                    )
                ).scalars()
            )
            missing = set(environment_ids) - known
            if missing:
                raise ValueError(
                    f"unknown rollout tenants: {', '.join(sorted(missing))}"
                )
            if not environment_ids:
                raise ValueError("a rollout requires at least one tenant")
            rollout_id = conn.execute(
                rollouts.insert().values(
                    release_json=json.dumps(asdict(release), sort_keys=True),
                    state=RolloutState.CANARY,
                    created_at=_now(),
                )
            ).inserted_primary_key[0]
            for index, environment_id in enumerate(sorted(environment_ids)):
                conn.execute(
                    migration_tasks.insert().values(
                        rollout_id=rollout_id,
                        environment_id=environment_id,
                        phase=(
                            RolloutPhase.CANARY
                            if index < canary_count
                            else RolloutPhase.FLEET
                        ),
                        state=MigrationState.PENDING,
                        attempts=0,
                        updated_at=_now(),
                    )
                )
            return int(rollout_id)

    def lease_tasks(
        self, rollout_id: int, owner: str, *, limit: int = 10, lease_seconds: int = 600
    ) -> list[dict[str, Any]]:
        """Lease up to ``limit`` tasks. PostgreSQL locks rows; SQLite supports tests."""
        if limit < 1:
            raise ValueError("limit must be at least one")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be at least one")
        with self.engine.begin() as conn:
            rollout = conn.execute(
                select(rollouts.c.state).where(rollouts.c.id == rollout_id)
            ).scalar_one()
            if rollout in {
                RolloutState.HALTED,
                RolloutState.COMPLETE,
                RolloutState.PAUSED,
            }:
                return []
            now = _now()
            conn.execute(
                update(migration_tasks)
                .where(
                    migration_tasks.c.rollout_id == rollout_id,
                    migration_tasks.c.state == MigrationState.LEASED,
                    migration_tasks.c.lease_expires_at < now,
                )
                .values(
                    state=MigrationState.PENDING,
                    lease_owner=None,
                    lease_expires_at=None,
                    updated_at=now,
                )
            )
            phase = (
                RolloutPhase.CANARY
                if rollout == RolloutState.CANARY
                else RolloutPhase.FLEET
            )
            query = (
                select(migration_tasks)
                .where(
                    migration_tasks.c.rollout_id == rollout_id,
                    migration_tasks.c.state == MigrationState.PENDING,
                    migration_tasks.c.phase == phase,
                )
                .order_by(migration_tasks.c.id)
                .limit(limit)
            )
            if conn.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            rows = list(conn.execute(query).mappings())
            for row in rows:
                conn.execute(
                    update(migration_tasks)
                    .where(
                        migration_tasks.c.id == row["id"],
                        migration_tasks.c.state == MigrationState.PENDING,
                    )
                    .values(
                        state=MigrationState.LEASED,
                        lease_owner=owner,
                        lease_expires_at=now + timedelta(seconds=lease_seconds),
                        attempts=row["attempts"] + 1,
                        updated_at=now,
                    )
                )
            return [dict(row) for row in rows]

    def complete_task(
        self,
        task_id: int,
        owner: str,
        *,
        revision: str | None,
        error: str | None = None,
        attempts: int | None = None,
    ) -> None:
        state = MigrationState.SUCCEEDED if error is None else MigrationState.FAILED
        with self.engine.begin() as conn:
            result = conn.execute(
                update(migration_tasks)
                .where(
                    migration_tasks.c.id == task_id,
                    migration_tasks.c.state == MigrationState.LEASED,
                    migration_tasks.c.lease_owner == owner,
                )
                .values(
                    state=state,
                    revision=revision,
                    error=error,
                    **({"attempts": attempts} if attempts is not None else {}),
                    lease_expires_at=None,
                    updated_at=_now(),
                )
            )
            if result.rowcount != 1:
                raise ValueError("task is not leased by this worker")
            if error is not None:
                conn.execute(
                    update(rollouts)
                    .where(
                        rollouts.c.id
                        == select(migration_tasks.c.rollout_id)
                        .where(migration_tasks.c.id == task_id)
                        .scalar_subquery()
                    )
                    .values(state=RolloutState.HALTED)
                )
            else:
                rollout_id = conn.execute(
                    select(migration_tasks.c.rollout_id).where(
                        migration_tasks.c.id == task_id
                    )
                ).scalar_one()
                self._advance_if_ready(conn, int(rollout_id))

    @staticmethod
    def _advance_if_ready(conn, rollout_id: int) -> None:
        """Advance canary only after every canary task has verified successfully."""
        rollout = conn.execute(
            select(rollouts.c.state).where(rollouts.c.id == rollout_id)
        ).scalar_one()
        phase = (
            RolloutPhase.CANARY
            if rollout == RolloutState.CANARY
            else RolloutPhase.FLEET
        )
        pending = conn.execute(
            select(migration_tasks.c.id).where(
                migration_tasks.c.rollout_id == rollout_id,
                migration_tasks.c.phase == phase,
                migration_tasks.c.state != MigrationState.SUCCEEDED,
            )
        ).first()
        if pending is not None:
            return
        if rollout == RolloutState.CANARY:
            has_fleet = conn.execute(
                select(migration_tasks.c.id).where(
                    migration_tasks.c.rollout_id == rollout_id,
                    migration_tasks.c.phase == RolloutPhase.FLEET,
                )
            ).first()
            conn.execute(
                update(rollouts)
                .where(rollouts.c.id == rollout_id)
                .values(
                    state=RolloutState.RUNNING if has_fleet else RolloutState.COMPLETE
                )
            )
        else:
            conn.execute(
                update(rollouts)
                .where(rollouts.c.id == rollout_id)
                .values(state=RolloutState.COMPLETE)
            )

    def resume_rollout(self, rollout_id: int) -> None:
        """Resume only a cleanly paused rollout; failures require a forward fix."""
        with self.engine.begin() as conn:
            failed = conn.execute(
                select(migration_tasks.c.id).where(
                    migration_tasks.c.rollout_id == rollout_id,
                    migration_tasks.c.state == MigrationState.FAILED,
                )
            ).first()
            if failed is not None:
                raise ValueError(
                    "failed migration requires a forward fix before resuming"
                )
            unfinished_canary = conn.execute(
                select(migration_tasks.c.id).where(
                    migration_tasks.c.rollout_id == rollout_id,
                    migration_tasks.c.phase == RolloutPhase.CANARY,
                    migration_tasks.c.state != MigrationState.SUCCEEDED,
                )
            ).first()
            result = conn.execute(
                update(rollouts)
                .where(
                    rollouts.c.id == rollout_id, rollouts.c.state == RolloutState.PAUSED
                )
                .values(
                    state=(
                        RolloutState.CANARY
                        if unfinished_canary is not None
                        else RolloutState.RUNNING
                    )
                )
            )
            if result.rowcount != 1:
                raise ValueError("only paused rollouts may be resumed")

    def pause_rollout(self, rollout_id: int) -> None:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(rollouts)
                .where(
                    rollouts.c.id == rollout_id,
                    rollouts.c.state.in_([RolloutState.CANARY, RolloutState.RUNNING]),
                )
                .values(state=RolloutState.PAUSED)
            )
            if result.rowcount != 1:
                raise ValueError("only active rollouts may be paused")

    def status(self, rollout_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            state = conn.execute(
                select(rollouts.c.state).where(rollouts.c.id == rollout_id)
            ).scalar_one()
            rows = conn.execute(
                select(migration_tasks.c.state, migration_tasks.c.phase).where(
                    migration_tasks.c.rollout_id == rollout_id
                )
            ).all()
        counts: dict[str, int] = {}
        for task_state, phase in rows:
            counts[f"{phase}:{task_state}"] = counts.get(f"{phase}:{task_state}", 0) + 1
        return {"rollout_id": rollout_id, "state": state, "tasks": counts}

    def assert_release_ready(
        self, rollout_id: int, artifact: "ReleaseArtifact"
    ) -> None:
        """Allow app deployment only after its exact compatible migration rollout."""
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(rollouts.c.state, rollouts.c.release_json).where(
                        rollouts.c.id == rollout_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise ValueError(f"unknown rollout: {rollout_id}")
        if row["state"] != RolloutState.COMPLETE:
            raise ValueError(
                "application rollout requires a completed migration rollout"
            )
        release = json.loads(row["release_json"])
        if (
            release["version"] != artifact.version
            or release["digest"] != artifact.digest
        ):
            raise ValueError(
                "application artifact does not match approved migration evidence"
            )

    def create_application_rollout(
        self,
        migration_rollout_id: int,
        release: ReleaseMetadata,
        environment_ids: list[str],
        *,
        canary_count: int = 1,
    ) -> int:
        """Create a progressive application rollout after compatible migrations."""
        if canary_count < 1 or not environment_ids:
            raise ValueError("an application rollout requires tenants and a canary")
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(rollouts.c.state, rollouts.c.release_json).where(
                        rollouts.c.id == migration_rollout_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None or row["state"] != RolloutState.COMPLETE:
                raise ValueError(
                    "application rollout requires a completed migration rollout"
                )
            if json.loads(row["release_json"]) != asdict(release):
                raise ValueError(
                    "application rollout release must match migration evidence"
                )
            migrated = set(
                conn.execute(
                    select(migration_tasks.c.environment_id).where(
                        migration_tasks.c.rollout_id == migration_rollout_id,
                        migration_tasks.c.state == MigrationState.SUCCEEDED,
                    )
                ).scalars()
            )
            if set(environment_ids) - migrated:
                raise ValueError(
                    "application rollout includes tenants without migration success"
                )
            rollout_id = conn.execute(
                application_rollouts.insert().values(
                    migration_rollout_id=migration_rollout_id,
                    release_json=json.dumps(asdict(release), sort_keys=True),
                    state=RolloutState.CANARY,
                    created_at=_now(),
                )
            ).inserted_primary_key[0]
            for index, environment_id in enumerate(sorted(environment_ids)):
                conn.execute(
                    application_tasks.insert().values(
                        application_rollout_id=rollout_id,
                        environment_id=environment_id,
                        phase=(
                            RolloutPhase.CANARY
                            if index < canary_count
                            else RolloutPhase.FLEET
                        ),
                        state=MigrationState.PENDING,
                        updated_at=_now(),
                    )
                )
        return int(rollout_id)

    def lease_application_tasks(
        self, rollout_id: int, owner: str, *, limit: int = 10, lease_seconds: int = 600
    ) -> list[dict[str, Any]]:
        if limit < 1 or lease_seconds < 1:
            raise ValueError("application lease limits must be positive")
        with self.engine.begin() as conn:
            state = conn.execute(
                select(application_rollouts.c.state).where(
                    application_rollouts.c.id == rollout_id
                )
            ).scalar_one()
            if state in {
                RolloutState.HALTED,
                RolloutState.COMPLETE,
                RolloutState.PAUSED,
            }:
                return []
            now = _now()
            conn.execute(
                update(application_tasks)
                .where(
                    application_tasks.c.application_rollout_id == rollout_id,
                    application_tasks.c.state == MigrationState.LEASED,
                    application_tasks.c.lease_expires_at < now,
                )
                .values(
                    state=MigrationState.PENDING,
                    lease_owner=None,
                    lease_expires_at=None,
                    updated_at=now,
                )
            )
            phase = (
                RolloutPhase.CANARY
                if state == RolloutState.CANARY
                else RolloutPhase.FLEET
            )
            query = (
                select(application_tasks)
                .where(
                    application_tasks.c.application_rollout_id == rollout_id,
                    application_tasks.c.state == MigrationState.PENDING,
                    application_tasks.c.phase == phase,
                )
                .order_by(application_tasks.c.id)
                .limit(limit)
            )
            if conn.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            rows = list(conn.execute(query).mappings())
            for row in rows:
                conn.execute(
                    update(application_tasks)
                    .where(application_tasks.c.id == row["id"])
                    .values(
                        state=MigrationState.LEASED,
                        lease_owner=owner,
                        lease_expires_at=now + timedelta(seconds=lease_seconds),
                        updated_at=now,
                    )
                )
            return [dict(row) for row in rows]

    def complete_application_task(
        self,
        task_id: int,
        owner: str,
        *,
        previous_digest: str | None,
        health_state: str,
        error: str | None = None,
        recovery_state: str | None = None,
    ) -> None:
        state = (
            MigrationState.SUCCEEDED
            if error is None and health_state == "passed"
            else MigrationState.FAILED
        )
        with self.engine.begin() as conn:
            task = (
                conn.execute(
                    select(application_tasks).where(application_tasks.c.id == task_id)
                )
                .mappings()
                .one_or_none()
            )
            if (
                task is None
                or task["state"] != MigrationState.LEASED
                or task["lease_owner"] != owner
            ):
                raise ValueError("application task is not leased by this worker")
            conn.execute(
                update(application_tasks)
                .where(application_tasks.c.id == task_id)
                .values(
                    state=state,
                    previous_digest=previous_digest,
                    health_state=health_state,
                    error=error,
                    recovery_state=recovery_state,
                    lease_expires_at=None,
                    updated_at=_now(),
                )
            )
            if state == MigrationState.FAILED:
                conn.execute(
                    update(application_rollouts)
                    .where(application_rollouts.c.id == task["application_rollout_id"])
                    .values(state=RolloutState.HALTED)
                )
                return
            self._advance_application_if_ready(
                conn, int(task["application_rollout_id"])
            )

    @staticmethod
    def _advance_application_if_ready(conn, rollout_id: int) -> None:
        state = conn.execute(
            select(application_rollouts.c.state).where(
                application_rollouts.c.id == rollout_id
            )
        ).scalar_one()
        phase = (
            RolloutPhase.CANARY if state == RolloutState.CANARY else RolloutPhase.FLEET
        )
        pending = conn.execute(
            select(application_tasks.c.id).where(
                application_tasks.c.application_rollout_id == rollout_id,
                application_tasks.c.phase == phase,
                application_tasks.c.state != MigrationState.SUCCEEDED,
            )
        ).first()
        if pending is not None:
            return
        if state == RolloutState.CANARY:
            fleet = conn.execute(
                select(application_tasks.c.id).where(
                    application_tasks.c.application_rollout_id == rollout_id,
                    application_tasks.c.phase == RolloutPhase.FLEET,
                )
            ).first()
            conn.execute(
                update(application_rollouts)
                .where(application_rollouts.c.id == rollout_id)
                .values(
                    state=RolloutState.RUNNING
                    if fleet is not None
                    else RolloutState.COMPLETE
                )
            )
        else:
            conn.execute(
                update(application_rollouts)
                .where(application_rollouts.c.id == rollout_id)
                .values(state=RolloutState.COMPLETE)
            )

    def application_status(self, rollout_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            state = conn.execute(
                select(application_rollouts.c.state).where(
                    application_rollouts.c.id == rollout_id
                )
            ).scalar_one()
            rows = conn.execute(
                select(
                    application_tasks.c.phase,
                    application_tasks.c.state,
                    application_tasks.c.recovery_state,
                ).where(application_tasks.c.application_rollout_id == rollout_id)
            ).all()
        counts: dict[str, int] = {}
        for phase, task_state, recovery in rows:
            counts[f"{phase}:{task_state}"] = counts.get(f"{phase}:{task_state}", 0) + 1
            if recovery:
                counts[f"recovery:{recovery}"] = (
                    counts.get(f"recovery:{recovery}", 0) + 1
                )
        return {"application_rollout_id": rollout_id, "state": state, "tasks": counts}

    def record_audit(
        self, environment_id: str, event: str, actor: str, evidence: dict[str, Any]
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                audit_events.insert().values(
                    environment_id=_opaque(environment_id),
                    event=_opaque(event),
                    actor=_opaque(actor),
                    evidence_json=json.dumps(evidence, sort_keys=True),
                    recorded_at=_now(),
                )
            )

    def database_resource_for(self, environment_id: str) -> str:
        with self.engine.connect() as conn:
            value = conn.execute(
                select(tenants.c.database_resource_id).where(
                    tenants.c.environment_id == environment_id
                )
            ).scalar_one_or_none()
        if value is None:
            raise ValueError(f"unknown tenant environment: {environment_id}")
        return str(value)


class FleetReleaseGate:
    """Bridge the durable fleet control plane into the runtime deployment path."""

    def __init__(
        self,
        plane: SqlControlPlane,
        rollout_id: int,
        *,
        actor: str,
        incident_reference: str,
    ) -> None:
        if not incident_reference.strip():
            raise ValueError("an incident or change reference is required")
        self.plane = plane
        self.rollout_id = rollout_id
        self.actor = _opaque(actor)
        self.incident_reference = incident_reference.strip()

    def __call__(self, environment_id: str, artifact: "ReleaseArtifact") -> None:
        self.plane.assert_release_ready(self.rollout_id, artifact)
        self.plane.record_audit(
            environment_id,
            "APPLICATION_RELEASE_GATED",
            self.actor,
            {
                "rollout_id": self.rollout_id,
                "incident_reference": self.incident_reference,
                "version": artifact.version,
                "digest": artifact.digest,
            },
        )


def sign_manual_provider_action(action: dict[str, Any], secret: str) -> dict[str, Any]:
    """Create a tamper-evident manual Darkube action without storing credentials."""
    payload = json.dumps(action, sort_keys=True, separators=(",", ":")).encode()
    return {
        **action,
        "signature": hmac.new(secret.encode(), payload, sha256).hexdigest(),
    }
