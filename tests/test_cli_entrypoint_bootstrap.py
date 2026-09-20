"""Guard the standalone-CLI interpreter bootstrap for the operator entry points.

The five operator CLIs in ``scripts/`` are run directly
(``python scripts/<name>.py``) from arbitrary working directories. Each one
begins with a ``__package__`` guard that puts the repository root on
``sys.path`` before importing ``src...``:

    if __package__ in {None, ""}:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

``scripts/deploy_saas_release.py`` was the only member of this family missing the
guard, which broke the release CLI whenever ``src`` was not already importable
(for example a plain interpreter invoked from outside the repository, or any
environment that does not add the project root to ``sys.path``).

Only this family is asserted. Other scripts under ``scripts/`` import ``src``
without the guard and rely on the environment for importability; requiring the
guard repo-wide would encode a rule the repository does not actually follow.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

import pytest

from src.saas.control_plane import ControlPlane
from src.saas.environment_contract import DeploymentProfile, EnvironmentManifest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"

# The operator CLI family: one-off, metadata-only SaaS operations.
OPERATOR_SCRIPTS = (
    "backup_saas_environment.py",
    "deploy_saas_release.py",
    "migrate_tenant_databases.py",
    "provision_saas_environment.py",
    "restore_saas_environment.py",
)


@pytest.mark.parametrize("script_name", OPERATOR_SCRIPTS)
def test_operator_script_has_the_interpreter_bootstrap(script_name: str) -> None:
    """The guard must be present, not merely working in this environment."""

    source = (SCRIPT_DIRECTORY / script_name).read_text(encoding="utf-8")

    assert '__package__ in {None, ""}' in source
    assert "sys.path.insert" in source


@pytest.mark.parametrize("script_name", OPERATOR_SCRIPTS)
def test_operator_script_starts_from_an_unrelated_directory(script_name: str) -> None:
    """``--help`` must reach the argument parser with no import failure.

    The working directory is a raw ``mkdtemp`` directory rather than ``tmp_path``
    because pytest's tmp factory root and the conftest temp redirect both live
    under ``.test-artifacts``, whose ACLs can be stale in sandboxed checkouts.
    Cleanup is best-effort so a teardown permission failure cannot mask a result.
    """

    unrelated_directory = tempfile.mkdtemp(prefix="cli-bootstrap-")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / script_name), "--help"],
            capture_output=True,
            text=True,
            cwd=unrelated_directory,
            check=False,
        )
    finally:
        shutil.rmtree(unrelated_directory, ignore_errors=True)

    assert "ModuleNotFoundError" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_deploy_and_restore_are_usable_subprocess_entry_points() -> None:
    """Regression: the release CLI must start, and restore must expose an action."""

    deploy = subprocess.run(
        [sys.executable, str(SCRIPT_DIRECTORY / "deploy_saas_release.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert deploy.returncode == 0, deploy.stderr
    assert "deploy" in deploy.stdout and "rollback" in deploy.stdout

    restore = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIRECTORY / "restore_saas_environment.py"),
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restore.returncode == 0, restore.stderr
    # Registration is the action that makes a restore reachable at all.
    assert "register-target" in restore.stdout
    assert "restore" in restore.stdout


def test_backup_restore_cli_round_trip_through_target_registration() -> None:
    """Regression for the unreachable restore path.

    ``RestoreManager`` refuses any target that was not registered first, and
    previously nothing outside the test suite could register one, so the restore
    CLI could never succeed.

    The environment must also exist in the control plane before a backup or
    restore will run: ``BackupManager``/``RestoreManager`` record provider
    metadata through ``ControlPlane.update_environment_metadata``, which raises
    ``EnvironmentNotFound`` for an unregistered environment. So the journey
    starts with ``provision``.

    The scratch parent is ``tmp/`` (already ignored) rather than the redirected
    stdlib temp root, because ``tests/conftest.py`` points ``tempfile.tempdir`` at
    ``.test-artifacts`` and directories created beneath it are not writable in a
    sandboxed checkout. ``mkdir`` is used instead of ``mkdtemp`` so the directory
    inherits the parent's permissions rather than a restrictive private ACL.
    """

    scratch_parent = ROOT / "tmp"
    scratch_parent.mkdir(exist_ok=True)
    workdir = scratch_parent / f"restore-journey-{uuid.uuid4().hex[:12]}"
    workdir.mkdir(parents=True)
    try:
        state_file = workdir / "backups.json"
        environment_state_file = workdir / "environments.json"
        control_plane_state_file = workdir / "control-plane.json"
        credential_file = workdir / "operators.json"
        manifest_file = workdir / "manifest.json"
        credential_file.write_text(
            json.dumps(
                {
                    "operators": [
                        {
                            "principal": "operator-a",
                            "token_sha256": hashlib.sha256(b"token-a").hexdigest(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        manifest_file.write_text(
            EnvironmentManifest(
                environment_id="env-a",
                customer_id="customer-a",
                deployment_profile=DeploymentProfile.SINGLE_TENANT_SAAS,
                application_version="release-1",
                database_resource_id="local-db:env-a",
            ).model_dump_json(),
            encoding="utf-8",
        )
        env = {**os.environ, "OKR_OPERATOR_TOKEN": "token-a"}

        def run(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIRECTORY / script),
                    *arguments,
                    "--credential-file",
                    str(credential_file),
                    "--control-plane-state-file",
                    str(control_plane_state_file),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                env=env,
                check=False,
            )

        provisioned = run(
            "provision_saas_environment.py",
            "provision",
            "--manifest",
            str(manifest_file),
            "--state-file",
            str(environment_state_file),
        )
        assert provisioned.returncode == 0, provisioned.stderr

        backup = run(
            "backup_saas_environment.py",
            "create",
            "--environment-id",
            "env-a",
            "--state-file",
            str(state_file),
            "--test-only",
        )
        assert backup.returncode == 0, backup.stderr
        backup_id = json.loads(backup.stdout)["backup_id"]

        # A restore before registration must fail closed.
        unregistered = run(
            "restore_saas_environment.py",
            "restore",
            "--backup-id",
            backup_id,
            "--environment-id",
            "env-a",
            "--isolated-target",
            "rehearsal-db-1",
            "--state-file",
            str(state_file),
            "--test-only",
        )
        assert unregistered.returncode != 0
        assert "not registered" in unregistered.stderr

        registered = run(
            "restore_saas_environment.py",
            "register-target",
            "--environment-id",
            "env-a",
            "--isolated-target",
            "rehearsal-db-1",
            "--state-file",
            str(state_file),
            "--test-only",
        )
        assert registered.returncode == 0, registered.stderr
        assert json.loads(registered.stdout)["registered"] is True

        # Registration must persist across processes for the restore to work.
        restore = run(
            "restore_saas_environment.py",
            "restore",
            "--backup-id",
            backup_id,
            "--environment-id",
            "env-a",
            "--isolated-target",
            "rehearsal-db-1",
            "--state-file",
            str(state_file),
            "--test-only",
        )
        assert restore.returncode == 0, restore.stderr
        outcome = json.loads(restore.stdout)
        assert outcome["target"] == "rehearsal-db-1"
        assert outcome["verified"] is True

        # The control plane must have recorded the restore against the environment.
        assert (
            ControlPlane(state_path=control_plane_state_file)
            .get_environment("env-a")
            .backup_state
            == "restore-tested"
        )

        # An unsafe target is rejected and must not be persisted.
        for unsafe_target in ("customer-prod-db", "live-db", "production"):
            rejected = run(
                "restore_saas_environment.py",
                "register-target",
                "--environment-id",
                "env-a",
                "--isolated-target",
                unsafe_target,
                "--state-file",
                str(state_file),
                "--test-only",
            )
            assert rejected.returncode != 0, unsafe_target
            assert "prohibited" in rejected.stderr
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
