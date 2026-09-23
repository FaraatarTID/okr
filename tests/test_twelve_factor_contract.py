from __future__ import annotations

from pathlib import Path

from scripts.verify_twelve_factor_contract import (
    _IMAGE_TARGETS,
    _run_release_renderer,
    _workload_image_digest,
    verify_repository,
)


_API_TARGET = _IMAGE_TARGETS["api_digest"]
_API_WORKLOAD = _API_TARGET.workload
_API_CONTAINER = _API_TARGET.container
_WORKER_WORKLOAD = _IMAGE_TARGETS["worker_digest"].workload
_WORKER_CONTAINER = _IMAGE_TARGETS["worker_digest"].container
# The unresolved placeholder the shipped manifests carry until the renderer substitutes it.
_PLACEHOLDER_IMAGE = "ghcr.io/example/okr@sha256:REPLACE_WITH_RELEASE_DIGEST"


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _valid_repository(root: Path) -> None:
    _write(root, "pyproject.toml", "[project]\ndependencies = []\n")
    _write(root, "uv.lock", "version = 1\n")
    _write(root, "package.json", '{"private": true}\n')
    _write(root, "package-lock.json", '{"lockfileVersion": 3}\n')
    _write(root, "spa-bff/package.json", '{"private": true}\n')
    _write(root, "spa-bff/package-lock.json", '{"lockfileVersion": 3}\n')
    _write(root, "spa-web/package.json", '{"private": true}\n')
    _write(root, "spa-web/package-lock.json", '{"lockfileVersion": 3}\n')
    _write(
        root, "deploy/docker/.env.example", "OKR_DATABASE_URL=\nBFF_SESSION_SECRET=\n"
    )
    _write(
        root,
        "deploy/docker/.env.saas.example",
        "OKR_DATABASE_URL=\nOKR_BACKEND_SERVICE_TOKEN=\n",
    )
    _write(
        root,
        "deploy/docker/docker-compose.yml",
        """
services:
  api:
    image: ${OKR_RELEASE_BACKEND_IMAGE:?required}
    environment:
      - OKR_DATABASE_URL=${OKR_DATABASE_URL:?required}
    ports:
      - "127.0.0.1:8100:8100"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/healthz"]
""",
    )
    _write(
        root,
        "deploy/docker/Dockerfile",
        "EXPOSE 8100\nHEALTHCHECK CMD curl -f http://localhost:8100/healthz\n",
    )
    _write(root, "spa-bff/Dockerfile", "EXPOSE 3001\n")
    _write(root, "spa-web/Dockerfile", "EXPOSE 3000\n")
    _write(
        root,
        "deploy/docker/docker-compose.release.yml",
        "\n".join(
            f"image: ${{{name}:?required}}"
            for name in (
                "OKR_RELEASE_BACKEND_IMAGE",
                "OKR_RELEASE_BFF_IMAGE",
                "OKR_RELEASE_WEB_IMAGE",
            )
        ),
    )
    _write(
        root,
        ".github/workflows/promote-production.yml",
        "image@sha256:${DIGEST}\nrelease_sha: ${{ inputs.release_sha }}\n",
    )
    _write(root, ".github/workflows/docker-deploy.yml", "sha256:[0-9a-fA-F]{64}\n")
    _write(
        root,
        "docs/saas/prerelease-runbook.md",
        "Run this one-off admin command:\n\n    alembic upgrade head\n",
    )


def test_valid_repository_passes() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _valid_repository(root)
        assert verify_repository(root) == []


def test_missing_lockfile_is_reported_without_file_contents(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    (tmp_path / "uv.lock").unlink()

    failures = verify_repository(tmp_path)

    assert any("dependency lockfiles" in failure for failure in failures)
    assert all("OKR_DATABASE_URL" not in failure for failure in failures)


def test_non_immutable_promotion_reference_is_reported(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    (tmp_path / ".github/workflows/promote-production.yml").write_text(
        "image: ghcr.io/example/okr:latest\n", encoding="utf-8"
    )

    failures = verify_repository(tmp_path)

    assert any("immutable image references" in failure for failure in failures)


def test_release_image_inputs_require_workflow_digest_validation(
    tmp_path: Path,
) -> None:
    _valid_repository(tmp_path)
    _write(
        tmp_path,
        ".github/workflows/docker-deploy.yml",
        "image validation sha256:[0-9a-fA-F]{64}\n",
    )
    overlay = tmp_path / "deploy/docker/docker-compose.release.yml"
    overlay.write_text(
        "\n".join(
            f"image: ${{{name}:?required}}"
            for name in (
                "OKR_RELEASE_BACKEND_IMAGE",
                "OKR_RELEASE_BFF_IMAGE",
                "OKR_RELEASE_WEB_IMAGE",
            )
        ),
        encoding="utf-8",
    )

    assert verify_repository(tmp_path) == []


def test_release_image_inputs_without_digest_validation_are_reported(
    tmp_path: Path,
) -> None:
    _valid_repository(tmp_path)
    _write(
        tmp_path,
        "deploy/docker/docker-compose.release.yml",
        "image: ${OKR_RELEASE_BACKEND_IMAGE:?required}\n"
        "image: ${OKR_RELEASE_BFF_IMAGE:?required}\n"
        "image: ${OKR_RELEASE_WEB_IMAGE:?required}\n",
    )
    _write(tmp_path, ".github/workflows/docker-deploy.yml", "required image inputs\n")

    failures = verify_repository(tmp_path)

    assert any("sha256 image digest syntax" in failure for failure in failures)


def test_web_mapping_must_target_configured_container_port(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    compose = tmp_path / "deploy/docker/docker-compose.yml"
    compose.write_text(
        (
            compose.read_text(encoding="utf-8")
            + "\n  spa-web:\n"
            + "    ports:\n"
            + '      - "${SPA_WEB_HOST_PORT:-3000}:3000"\n'
        ),
        encoding="utf-8",
    )

    failures = verify_repository(tmp_path)

    assert any("spa-web port mapping" in failure for failure in failures)


def test_missing_healthcheck_and_admin_command_are_reported(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    compose = tmp_path / "deploy/docker/docker-compose.yml"
    compose.write_text(
        "services:\n  api:\n    ports: ['8100:8100']\n", encoding="utf-8"
    )
    (tmp_path / "deploy/docker/Dockerfile").write_text(
        "EXPOSE 8100\n", encoding="utf-8"
    )
    (tmp_path / "docs/saas/prerelease-runbook.md").write_text(
        "Use the admin console.\n", encoding="utf-8"
    )

    failures = verify_repository(tmp_path)

    assert any("healthchecks" in failure for failure in failures)
    assert any("one-off admin command" in failure for failure in failures)


def test_secret_like_values_are_not_echoed_in_failures(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    secret = "super-secret-value-123"
    (tmp_path / "deploy/docker/.env.example").write_text(
        f"OKR_BACKEND_SERVICE_TOKEN={secret}\n", encoding="utf-8"
    )

    failures = verify_repository(tmp_path)

    assert secret not in "\n".join(failures)


def _k8s_manifests(root: Path) -> None:
    """Create the manifests whose presence activates the release-renderer check.

    Each declares the workload identity the contract expects - apiVersion, kind, and
    metadata.name - and carries the unresolved digest placeholder on the container the
    checker expects for that workload, so a renderer that never substitutes anything cannot
    pass by accident and the target container is identifiable by name.
    """
    for name, workload, container in (
        ("deployment-backend-api.yaml", _API_WORKLOAD, _API_CONTAINER),
        ("deployment-backend-worker.yaml", _WORKER_WORKLOAD, _WORKER_CONTAINER),
    ):
        _write(
            root,
            f"deploy/k8s/{name}",
            _deployment(workload, [(container, _PLACEHOLDER_IMAGE)]),
        )


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _install_real_renderer(root: Path) -> None:
    """Install the shipped renderer, so the check exercises real validation code."""

    _write(
        root,
        "scripts/render_k8s_release.py",
        (_REPO_ROOT / "scripts/render_k8s_release.py").read_text(encoding="utf-8"),
    )


def _legacy_substrings_present(root: Path) -> bool:
    """The exact predicate the previous source substring check used.

    Every fixture below that must be *rejected* is asserted to satisfy this, so each test
    demonstrates detection of a renderer the old check would have accepted.
    """

    source = (root / "scripts/render_k8s_release.py").read_text(encoding="utf-8")
    return "64" in source and "REPLACE_WITH_RELEASE_DIGEST" in source


# Renders faithfully but never validates a digest. Holds both strings the previous check
# searched for, so that check accepted it.
_RENDER_WITHOUT_VALIDATION = """import argparse
from pathlib import Path

# Intended rule: ^[0-9a-f]{64}$  (validation deliberately absent in this fixture)
PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    values = {
        "deployment-backend-api.yaml": args.api_digest.removeprefix("sha256:"),
        "deployment-backend-worker.yaml": args.worker_digest.removeprefix("sha256:"),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, digest in values.items():
        source = (root / "deploy" / "k8s" / filename).read_text(encoding="utf-8")
        (args.output_dir / filename).write_text(
            source.replace(PLACEHOLDER, digest), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

# Declares the right strings and renders nothing: precisely what the previous check
# accepted, and the reason it certified a renderer that could not render.
_SUBSTRINGS_ONLY = (
    'PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"\nPATTERN = r"[0-9a-f]{64}"\n'
)

# Validates one label and ignores the other, so the two inputs must be probed separately.
_VALIDATE_ONLY_ONE = """import argparse
import re
from pathlib import Path

PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _validate(value, label):
    digest = value.removeprefix("sha256:")
    if label == "__LABEL__":
        if not DIGEST.fullmatch(digest):
            raise ValueError(f"{label} must be a 64-character hexadecimal sha256 digest")
    return digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    values = {
        "deployment-backend-api.yaml": _validate(args.api_digest, "api_digest"),
        "deployment-backend-worker.yaml": _validate(args.worker_digest, "worker_digest"),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, digest in values.items():
        source = (root / "deploy" / "k8s" / filename).read_text(encoding="utf-8")
        rendered = source.replace(PLACEHOLDER, digest)
        if PLACEHOLDER in rendered:
            raise ValueError(f"unresolved digest placeholder remains in {filename}")
        (args.output_dir / filename).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

# Fails on an invalid digest for a reason that names nothing: an unattributable non-zero
# exit, which must not be read as a rejection of the digest.
_CRASH_WITHOUT_NAMING = """import argparse
import re
from pathlib import Path

PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    supplied = [
        args.api_digest.removeprefix("sha256:"),
        args.worker_digest.removeprefix("sha256:"),
    ]
    if not all(DIGEST.fullmatch(value) for value in supplied):
        raise RuntimeError("unexpected failure while preparing manifests")
    root = Path(__file__).resolve().parents[1]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, digest in zip(
        ("deployment-backend-api.yaml", "deployment-backend-worker.yaml"), supplied
    ):
        source = (root / "deploy" / "k8s" / filename).read_text(encoding="utf-8")
        (args.output_dir / filename).write_text(
            source.replace(PLACEHOLDER, digest), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

# Validates both labels correctly but writes the source verbatim, so the placeholder ships.
_SHIP_THE_PLACEHOLDER = """import argparse
import re
from pathlib import Path

PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _validate(value, label):
    digest = value.removeprefix("sha256:")
    if not DIGEST.fullmatch(digest):
        raise ValueError(f"{label} must be a 64-character hexadecimal sha256 digest")
    return digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    _validate(args.api_digest, "api_digest")
    _validate(args.worker_digest, "worker_digest")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("deployment-backend-api.yaml", "deployment-backend-worker.yaml"):
        source = (root / "deploy" / "k8s" / filename).read_text(encoding="utf-8")
        (args.output_dir / filename).write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

_GUARD_BLOCK = (
    "        if _PLACEHOLDER in rendered:\n"
    '            raise ValueError(f"unresolved digest placeholder remains in {filename}")\n'
)


def _renderer_path(root: Path) -> Path:
    return root / "scripts/render_k8s_release.py"


def _bypass_validation(root: Path) -> None:
    """Make validation a pass-through, which is the only way to reach the guard.

    The guard at render_k8s_release.py:37 executes only when the rendered text still holds
    the placeholder, which requires the replacement text to be the placeholder itself -
    something _validate_digest refuses. The override is inserted before the entrypoint so
    it is in place when main() runs.
    """

    path = _renderer_path(root)
    source = path.read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":'
    assert marker in source, (
        "fixture no longer matches the shipped renderer's entrypoint"
    )
    override = (
        "def _validate_digest(value, label):\n"
        "    # Fixture only: validation deliberately bypassed to reach the guard.\n"
        "    return value.removeprefix('sha256:')\n\n\n"
    )
    path.write_text(source.replace(marker, override + marker), encoding="utf-8")


def _remove_placeholder_guard(root: Path) -> None:
    """Delete only the guard block, leaving every source string in place."""

    path = _renderer_path(root)
    source = path.read_text(encoding="utf-8")
    assert _GUARD_BLOCK in source, (
        "fixture no longer matches the shipped renderer's guard"
    )
    path.write_text(source.replace(_GUARD_BLOCK, ""), encoding="utf-8")


def test_k8s_manifests_without_a_renderer_are_reported(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)

    failures = verify_repository(tmp_path)

    assert any("digest validation" in failure for failure in failures), failures


def test_the_shipped_renderer_is_accepted(tmp_path: Path) -> None:
    # The acceptance half, driven by running the real renderer rather than by noticing
    # strings in its source. Without it, the tests below pass just as well against a
    # check that always reports a failure whenever the manifests exist.
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _install_real_renderer(tmp_path)

    assert verify_repository(tmp_path) == []


def test_a_renderer_that_renders_nothing_is_rejected(tmp_path: Path) -> None:
    # This module was accepted by the previous check, because it contains "64" and
    # "REPLACE_WITH_RELEASE_DIGEST". It cannot validate or render anything.
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(tmp_path, "scripts/render_k8s_release.py", _SUBSTRINGS_ONLY)
    assert _legacy_substrings_present(tmp_path), "premise: the old check accepted this"

    failures = verify_repository(tmp_path)

    assert any("did not produce" in failure for failure in failures), failures


def test_a_renderer_that_renders_without_validating_is_rejected(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(tmp_path, "scripts/render_k8s_release.py", _RENDER_WITHOUT_VALIDATION)
    assert _legacy_substrings_present(tmp_path), "premise: the old check accepted this"

    failures = verify_repository(tmp_path)

    assert any("accepted an invalid api_digest" in failure for failure in failures), (
        failures
    )


def test_only_the_api_digest_being_validated_is_reported_for_the_worker(
    tmp_path: Path,
) -> None:
    # Both inputs must be probed with the other one valid, otherwise a renderer that
    # checks only api_digest passes on the strength of the input it does check.
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(
        tmp_path,
        "scripts/render_k8s_release.py",
        _VALIDATE_ONLY_ONE.replace("__LABEL__", "api_digest"),
    )

    failures = verify_repository(tmp_path)

    assert any(
        "accepted an invalid worker_digest" in failure for failure in failures
    ), failures
    assert not any("accepted an invalid api_digest" in failure for failure in failures)


def test_only_the_worker_digest_being_validated_is_reported_for_the_api(
    tmp_path: Path,
) -> None:
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(
        tmp_path,
        "scripts/render_k8s_release.py",
        _VALIDATE_ONLY_ONE.replace("__LABEL__", "worker_digest"),
    )

    failures = verify_repository(tmp_path)

    assert any("accepted an invalid api_digest" in failure for failure in failures), (
        failures
    )
    assert not any(
        "accepted an invalid worker_digest" in failure for failure in failures
    )


def test_an_unattributed_failure_is_not_read_as_a_rejection(tmp_path: Path) -> None:
    # A non-zero exit that never names the offending input is not evidence that the digest
    # was rejected. Treating it as one would let any unrelated crash certify validation.
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(tmp_path, "scripts/render_k8s_release.py", _CRASH_WITHOUT_NAMING)

    failures = verify_repository(tmp_path)

    assert any(
        "cannot be attributed to digest validation" in failure for failure in failures
    ), failures
    assert not any(
        "does not enforce digest validation" in failure for failure in failures
    ), failures


def test_a_renderer_that_ships_the_unresolved_placeholder_is_rejected(
    tmp_path: Path,
) -> None:
    # Validation is intact here, so only the output-level placeholder inspection catches
    # this. The source strings the old check searched for are still present.
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(tmp_path, "scripts/render_k8s_release.py", _SHIP_THE_PLACEHOLDER)
    assert _legacy_substrings_present(tmp_path), "premise: the old check accepted this"

    failures = verify_repository(tmp_path)

    assert any("unresolved digest placeholder" in failure for failure in failures), (
        failures
    )


def test_the_placeholder_guard_is_reached_only_when_validation_is_bypassed(
    tmp_path: Path,
) -> None:
    """Show what actually exercises the guard at render_k8s_release.py:37.

    A normal, replaceable placeholder does not: validation refuses it first, so the
    guard's branch never runs and a test built on the ordinary path would prove nothing
    about it. The branch is reachable only after validation is bypassed, demonstrated
    here instead of assumed.
    """
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _install_real_renderer(tmp_path)
    outputs = tmp_path / "outputs"

    # Ordinary path: an unresolved placeholder is refused by validation, not by the guard.
    blocked_dir = outputs / "blocked"
    blocked = _run_release_renderer(
        tmp_path,
        api_digest="REPLACE_WITH_RELEASE_DIGEST",
        worker_digest="2" * 64,
        output_dir=blocked_dir,
    )
    assert blocked.executed
    assert blocked.returncode != 0
    assert "unresolved digest placeholder remains" not in blocked.output
    # Validation runs before the output directory is created.
    assert not blocked_dir.exists()

    # Guard reached: validation bypassed, so the placeholder survives replacement.
    _bypass_validation(tmp_path)
    reached_dir = outputs / "reached"
    reached = _run_release_renderer(
        tmp_path,
        api_digest="REPLACE_WITH_RELEASE_DIGEST",
        worker_digest="2" * 64,
        output_dir=reached_dir,
    )
    assert reached.executed
    assert reached.returncode != 0
    assert (
        "unresolved digest placeholder remains in deployment-backend-api.yaml"
        in reached.output
    ), reached.output
    # The guard fires before any manifest is written.
    assert not list(reached_dir.glob("*.yaml"))

    # Load-bearing: with the guard gone the placeholder reaches the output file.
    _remove_placeholder_guard(tmp_path)
    shipped_dir = outputs / "shipped"
    shipped = _run_release_renderer(
        tmp_path,
        api_digest="REPLACE_WITH_RELEASE_DIGEST",
        worker_digest="2" * 64,
        output_dir=shipped_dir,
    )
    assert shipped.executed
    assert shipped.returncode == 0
    assert "REPLACE_WITH_RELEASE_DIGEST" in (
        shipped_dir / "deployment-backend-api.yaml"
    ).read_text(encoding="utf-8")


# Validates both labels correctly and pins *a* digest in the image, but not the one the
# caller asked for: the requested digest is only quoted in a comment.
_COMMENT_ONLY_DIGEST = """import argparse
import re
from pathlib import Path

PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"
DIGEST = re.compile(r"^[0-9a-f]{64}$")
UNRELATED = "0" * 64


def _validate(value, label):
    digest = value.removeprefix("sha256:")
    if not DIGEST.fullmatch(digest):
        raise ValueError(f"{label} must be a 64-character hexadecimal sha256 digest")
    return digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--worker-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    requested = {
        "deployment-backend-api.yaml": _validate(args.api_digest, "api_digest"),
        "deployment-backend-worker.yaml": _validate(args.worker_digest, "worker_digest"),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, digest in requested.items():
        source = (root / "deploy" / "k8s" / filename).read_text(encoding="utf-8")
        rendered = source.replace(PLACEHOLDER, UNRELATED)
        (args.output_dir / filename).write_text(
            "# requested digest: " + digest + "\\n" + rendered, encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def test_a_digest_quoted_only_in_a_comment_does_not_satisfy_the_contract(
    tmp_path: Path,
) -> None:
    """A digest somewhere in the file is not a digest pinning a container image."""
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _write(tmp_path, "scripts/render_k8s_release.py", _COMMENT_ONLY_DIGEST)

    requested = "1" * 64
    outcome = _run_release_renderer(
        tmp_path,
        api_digest=requested,
        worker_digest="2" * 64,
        output_dir=tmp_path / "out",
    )
    assert outcome.executed
    assert outcome.returncode == 0
    rendered = (tmp_path / "out" / "deployment-backend-api.yaml").read_text(
        encoding="utf-8"
    )
    # Premise, asserted rather than assumed: the requested digest IS in the file text, so a
    # whole-file substring search would have accepted this manifest, while the target
    # container's own image pins a different digest.
    assert requested in rendered
    target_digest, target_reason = _workload_image_digest(rendered, _API_TARGET)
    assert target_reason is None
    assert target_digest == "0" * 64
    assert target_digest != requested

    failures = verify_repository(tmp_path)

    assert any(
        "does not pin the validated digest" in failure for failure in failures
    ), failures


def test_the_negative_input_is_malformed_content_not_a_missing_argument(
    tmp_path: Path,
) -> None:
    """The invalid-input probes must reach validation rather than argparse.

    argparse rejects a *missing* argument with exit code 2 and an "are required" message.
    That is an execution failure, not a digest rejection, and it must not be counted as
    one. The probe supplies malformed content instead, so it reaches validation.
    """
    _valid_repository(tmp_path)
    _k8s_manifests(tmp_path)
    _install_real_renderer(tmp_path)

    outcome = _run_release_renderer(
        tmp_path,
        api_digest="not-a-sha256-digest",
        worker_digest="2" * 64,
        output_dir=tmp_path / "out",
    )

    assert outcome.executed
    assert outcome.returncode != 0
    assert outcome.returncode != 2, "argparse rejected the argument, not validation"
    assert "are required" not in outcome.output
    assert "api_digest" in outcome.output


def _manifest(
    workload: str,
    spec: str,
    *,
    api_version: str = "apps/v1",
    kind: str = "Deployment",
) -> str:
    """Render a workload with the identity the contract expects, plus the given ``spec``."""

    return (
        f"apiVersion: {api_version}\n"
        f"kind: {kind}\n"
        "metadata:\n"
        f"  name: {workload}\n"
        "spec:\n"
        f"{spec}"
    )


def _pod_spec(
    containers: list[tuple[str, str]],
    init_containers: list[tuple[str, str]] | None = None,
) -> str:
    """Render the ``spec`` subtree holding ``template.spec.containers``, shipped shape."""

    lines = ["  template:", "    spec:"]
    if init_containers:
        lines.append("      initContainers:")
        for name, image in init_containers:
            lines.append(f"        - name: {name}")
            lines.append(f"          image: {image}")
    lines.append("      containers:")
    for name, image in containers:
        lines.append(f"        - name: {name}")
        lines.append(f"          image: {image}")
    return "\n".join(lines) + "\n"


def _deployment(
    workload: str,
    containers: list[tuple[str, str]],
    init_containers: list[tuple[str, str]] | None = None,
) -> str:
    """Render a Deployment in the shipped manifests' shape, one entry per container."""

    return _manifest(workload, _pod_spec(containers, init_containers))


def _pinned(workload: str, container: str) -> str:
    return _deployment(workload, [(container, _PLACEHOLDER_IMAGE)])


_PINNED_API = _pinned(_API_WORKLOAD, _API_CONTAINER)
_PINNED_WORKER = _pinned(_WORKER_WORKLOAD, _WORKER_CONTAINER)


def _install_manifests(root: Path, api: str, worker: str) -> None:
    _valid_repository(root)
    _install_real_renderer(root)
    _write(root, "deploy/k8s/deployment-backend-api.yaml", api)
    _write(root, "deploy/k8s/deployment-backend-worker.yaml", worker)


def _pinning_failures(failures: list[str]) -> list[str]:
    return [
        failure
        for failure in failures
        if failure.startswith("immutable image references")
    ]


def test_a_digest_on_a_sidecar_does_not_pin_the_workload_container(
    tmp_path: Path,
) -> None:
    """The bypass the file-wide search could not catch.

    The requested digest IS present in an image value, so a search across every image in
    the file accepts this manifest - but it pins the sidecar, and the workload the digest
    was minted for stays on a mutable tag.
    """
    _install_manifests(
        tmp_path,
        _deployment(
            _API_WORKLOAD,
            [
                ("backend-api", "ghcr.io/example/okr-backend:latest"),
                (
                    "log-shipper",
                    "ghcr.io/example/log-shipper@sha256:REPLACE_WITH_RELEASE_DIGEST",
                ),
            ],
        ),
        _PINNED_WORKER,
    )

    # Premise, asserted rather than assumed: the old whole-file search would have passed.
    outcome = _run_release_renderer(
        tmp_path,
        api_digest="1" * 64,
        worker_digest="2" * 64,
        output_dir=tmp_path / "out",
    )
    assert outcome.executed
    assert outcome.returncode == 0
    rendered = (tmp_path / "out" / "deployment-backend-api.yaml").read_text(
        encoding="utf-8"
    )
    assert f"log-shipper@sha256:{'1' * 64}" in rendered
    assert "ghcr.io/example/okr-backend:latest" in rendered
    # The requested digest pins the sidecar while the target container's own image is not
    # pinned at all, which is the state a search across every image value cannot tell apart.
    target_digest, target_reason = _workload_image_digest(rendered, _API_TARGET)
    assert target_digest is None
    assert target_reason is not None

    failures = verify_repository(tmp_path)

    assert any(
        "does not pin the validated digest" in failure and "'backend-api'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_digest_on_an_init_container_does_not_pin_the_workload_container(
    tmp_path: Path,
) -> None:
    """An initContainer is not the workload, so its digest must not satisfy the contract."""

    _install_manifests(
        tmp_path,
        _deployment(
            _API_WORKLOAD,
            [("backend-api", "ghcr.io/example/okr-backend:latest")],
            init_containers=[
                (
                    "migrate",
                    "ghcr.io/example/okr-backend@sha256:REPLACE_WITH_RELEASE_DIGEST",
                )
            ],
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "does not pin the validated digest" in failure and "'backend-api'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_unrelated_sidecars_leave_a_correctly_pinned_workload_accepted(
    tmp_path: Path,
) -> None:
    """Binding to the declared container must not reject an ordinary multi-container pod."""

    _install_manifests(
        tmp_path,
        _deployment(
            _API_WORKLOAD,
            [
                (
                    "backend-api",
                    "ghcr.io/example/okr-backend@sha256:REPLACE_WITH_RELEASE_DIGEST",
                ),
                ("log-shipper", "ghcr.io/example/log-shipper:1.2.3"),
                ("metrics", "ghcr.io/example/metrics@sha256:" + "9" * 64),
            ],
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert _pinning_failures(failures) == [], failures


def test_a_manifest_without_the_expected_container_is_reported_clearly(
    tmp_path: Path,
) -> None:
    """A differently named container holding the digest must not be read as the target."""

    _install_manifests(
        tmp_path,
        _deployment(
            _API_WORKLOAD,
            [
                (
                    "some-other-container",
                    "ghcr.io/example/okr-backend@sha256:REPLACE_WITH_RELEASE_DIGEST",
                )
            ],
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "no container named 'backend-api'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_manifest_with_two_same_named_containers_is_reported_clearly(
    tmp_path: Path,
) -> None:
    """Duplicate identities are ambiguous, so they are reported rather than resolved."""

    _install_manifests(
        tmp_path,
        _deployment(
            _API_WORKLOAD,
            [
                (
                    "backend-api",
                    "ghcr.io/example/okr-backend@sha256:REPLACE_WITH_RELEASE_DIGEST",
                ),
                ("backend-api", "ghcr.io/example/okr-backend:latest"),
            ],
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "more than one container named 'backend-api'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_manifest_without_a_pod_containers_list_is_reported_clearly(
    tmp_path: Path,
) -> None:
    _install_manifests(
        tmp_path,
        _manifest(
            _API_WORKLOAD, "  template:\n    spec:\n      restartPolicy: Always\n"
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "does not declare 'spec.template.spec.containers'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_the_worker_target_is_verified_independently_of_the_api(tmp_path: Path) -> None:
    """A correct api manifest must not cover for a worker pinned only on a sidecar."""

    _install_manifests(
        tmp_path,
        _pinned(_API_WORKLOAD, _API_CONTAINER),
        _deployment(
            _WORKER_WORKLOAD,
            [
                ("backend-worker", "ghcr.io/example/okr-worker:latest"),
                (
                    "log-shipper",
                    "ghcr.io/example/log-shipper@sha256:REPLACE_WITH_RELEASE_DIGEST",
                ),
            ],
        ),
    )

    failures = verify_repository(tmp_path)

    assert any(
        "deployment-backend-worker.yaml" in failure
        and "'backend-worker'" in failure
        and "does not pin the validated digest" in failure
        for failure in _pinning_failures(failures)
    ), failures
    assert not [
        failure
        for failure in _pinning_failures(failures)
        if "deployment-backend-api.yaml" in failure
    ], failures


# The shipped manifests' shape: nested mappings and nested lists inside the container.
_NESTED_MAPPINGS = _manifest(
    _API_WORKLOAD,
    "  template:\n"
    "    spec:\n"
    "      containers:\n"
    "        - name: backend-api\n"
    "          image: ghcr.io/example/okr-backend@sha256:REPLACE_WITH_RELEASE_DIGEST\n"
    "          imagePullPolicy: Always\n"
    "          ports:\n"
    "            - containerPort: 8100\n"
    "          env:\n"
    "            - name: OKR_DATABASE_URL\n"
    "              valueFrom:\n"
    "                secretKeyRef:\n"
    "                  name: okr-db\n"
    "                  key: OKR_DATABASE_URL\n"
    "          resources:\n"
    "            requests:\n"
    "              cpu: 100m\n",
)


def test_nested_mappings_inside_the_target_container_are_not_read_as_its_identity(
    tmp_path: Path,
) -> None:
    """`valueFrom.secretKeyRef.name` is not the container's name.

    The shipped manifests nest a `name:` under `env[].valueFrom.secretKeyRef`, so a reader
    that credited nested mapping keys to the container would invent a second name and fail
    the real repository.
    """
    _install_manifests(tmp_path, _NESTED_MAPPINGS, _PINNED_WORKER)

    failures = verify_repository(tmp_path)

    assert _pinning_failures(failures) == [], failures


# The workload identity the contract states, so a correctly *named* file holding another
# object cannot satisfy the check. Each case below pins the right container correctly, so
# only the identity or the path under test can explain the rejection.
def _pinned_pod_spec() -> str:
    return _pod_spec([(_API_CONTAINER, _PLACEHOLDER_IMAGE)])


def test_a_wrong_workload_kind_is_rejected(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest(_API_WORKLOAD, _pinned_pod_spec(), kind="ConfigMap"),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "does not declare 'kind: Deployment'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_wrong_api_version_is_rejected(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest(_API_WORKLOAD, _pinned_pod_spec(), api_version="v1"),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "does not declare 'apiVersion: apps/v1'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_wrong_workload_name_is_rejected(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest("some-other-workload", _pinned_pod_spec()),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "is not the workload named 'okr-backend-api'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_containers_list_outside_the_pod_spec_is_rejected(tmp_path: Path) -> None:
    """A `containers` key in an unrelated mapping is not the pod's container list.

    The digest sits on a container of the expected name, inside a correctly named file, so
    only walking the real `spec.template.spec` path distinguishes this from a valid
    manifest.
    """

    api = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: okr-backend-api\n"
        "  annotations:\n"
        "    containers:\n"
        f"      - name: {_API_CONTAINER}\n"
        f"        image: {_PLACEHOLDER_IMAGE}\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      restartPolicy: Always\n"
    )
    # Premise, asserted rather than assumed: the file does carry a containers list, with the
    # expected container name and the placeholder, so only the path check can reject it.
    assert f"image: {_PLACEHOLDER_IMAGE}" in api

    _install_manifests(tmp_path, api, _PINNED_WORKER)

    failures = verify_repository(tmp_path)

    assert any(
        "does not declare 'spec.template.spec.containers'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_containers_list_directly_under_spec_is_rejected(tmp_path: Path) -> None:
    """`spec.containers` is not `spec.template.spec.containers`."""

    _install_manifests(
        tmp_path,
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: okr-backend-api\n"
        "spec:\n"
        "  containers:\n"
        f"    - name: {_API_CONTAINER}\n"
        f"      image: {_PLACEHOLDER_IMAGE}\n",
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "does not declare 'spec.template'" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_malformed_manifest_is_rejected_as_invalid_yaml(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest(
            _API_WORKLOAD,
            "  template:\n"
            "    spec:\n"
            "      containers: [\n"
            f"        {{name: {_API_CONTAINER}, image: {_PLACEHOLDER_IMAGE}}}\n",
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "is not valid YAML" in failure for failure in _pinning_failures(failures)
    ), failures


def test_a_tab_indented_manifest_is_rejected(tmp_path: Path) -> None:
    """YAML forbids tabs as indentation, so this must not be read as structure.

    A reader that counted tab characters as indentation would accept this manifest while
    every YAML tooling the cluster uses would refuse to parse it.
    """

    _install_manifests(
        tmp_path,
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: okr-backend-api\n"
        "spec:\n"
        "\ttemplate:\n"
        "\t\tspec:\n"
        "\t\t\tcontainers:\n"
        f"\t\t\t\t- name: {_API_CONTAINER}\n"
        f"\t\t\t\t  image: {_PLACEHOLDER_IMAGE}\n",
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "is not valid YAML" in failure for failure in _pinning_failures(failures)
    ), failures


def test_a_manifest_with_several_documents_is_rejected(tmp_path: Path) -> None:
    """Two documents leave the deployed object ambiguous, so neither may be assumed."""

    _install_manifests(
        tmp_path,
        _manifest(_API_WORKLOAD, _pinned_pod_spec())
        + "---\n"
        + _manifest(_API_WORKLOAD, _pinned_pod_spec()),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "is not valid YAML" in failure for failure in _pinning_failures(failures)
    ), failures


def test_a_duplicate_mapping_key_is_rejected(tmp_path: Path) -> None:
    """A repeated `image` key must not be resolved by keeping one of the two values.

    The placeholder is last, so a last-value-wins reader would have accepted a manifest whose
    intended image is genuinely ambiguous.
    """

    api = _manifest(
        _API_WORKLOAD,
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        f"        - name: {_API_CONTAINER}\n"
        "          image: ghcr.io/example/okr-backend:latest\n"
        f"          image: {_PLACEHOLDER_IMAGE}\n",
    )
    # Premise: the expected value is the *last* one, so last-wins would have passed.
    assert api.index("latest") < api.index(_PLACEHOLDER_IMAGE)

    _install_manifests(tmp_path, api, _PINNED_WORKER)

    failures = verify_repository(tmp_path)

    assert any(
        "duplicate mapping key" in failure for failure in _pinning_failures(failures)
    ), failures


def test_an_image_inside_a_block_scalar_does_not_pin_the_container(
    tmp_path: Path,
) -> None:
    """A pinned image written into a string is text, not the container's image."""

    api = _manifest(
        _API_WORKLOAD,
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        f"        - name: {_API_CONTAINER}\n"
        "          image: ghcr.io/example/okr-backend:latest\n"
        "          notes: |\n"
        f"            image: {_PLACEHOLDER_IMAGE}\n",
    )
    # Premise: the placeholder is in the file, so only reading it as a string rejects this.
    assert _PLACEHOLDER_IMAGE in api

    _install_manifests(tmp_path, api, _PINNED_WORKER)

    failures = verify_repository(tmp_path)

    assert any(
        "is not pinned to a sha256 digest" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_containers_fragment_inside_a_block_scalar_is_not_read_as_a_list(
    tmp_path: Path,
) -> None:
    """A `containers:` line inside a string is a string, not a second container list.

    The target container is pinned correctly, so reading the string as another list would
    reject a manifest that is exactly right.
    """

    _install_manifests(
        tmp_path,
        _manifest(
            _API_WORKLOAD,
            "  template:\n"
            "    spec:\n"
            "      containers:\n"
            f"        - name: {_API_CONTAINER}\n"
            f"          image: {_PLACEHOLDER_IMAGE}\n"
            "      notes: |\n"
            "        containers:\n"
            "          - name: decoy\n",
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert _pinning_failures(failures) == [], failures


def test_flow_style_containers_are_read_structurally(tmp_path: Path) -> None:
    """Valid YAML the hand-written reader could not parse is now interpreted, not refused."""

    _install_manifests(
        tmp_path,
        _manifest(
            _API_WORKLOAD,
            "  template:\n"
            "    spec:\n"
            f'      containers: [{{name: {_API_CONTAINER}, image: "{_PLACEHOLDER_IMAGE}"}}]\n',
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert _pinning_failures(failures) == [], failures


def test_a_container_entry_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest(
            _API_WORKLOAD,
            "  template:\n    spec:\n      containers: [backend-api]\n",
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "containers[0]' is not a mapping" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_containers_that_is_not_a_list_is_rejected(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest(_API_WORKLOAD, "  template:\n    spec:\n      containers: {}\n"),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "does not declare 'spec.template.spec.containers' as a list" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_an_empty_containers_list_is_rejected(tmp_path: Path) -> None:
    _install_manifests(
        tmp_path,
        _manifest(_API_WORKLOAD, "  template:\n    spec:\n      containers: []\n"),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "empty 'spec.template.spec.containers' list" in failure
        for failure in _pinning_failures(failures)
    ), failures


def test_a_rejection_does_not_echo_manifest_content(tmp_path: Path) -> None:
    """Parse failures are reported by problem and position, never by reproducing a line."""

    _install_manifests(
        tmp_path,
        _manifest(
            _API_WORKLOAD,
            "  template:\n"
            "    spec:\n"
            "      containers: [\n"
            "        {name: backend-api, image: okr-database-url-secret-value}\n",
        ),
        _PINNED_WORKER,
    )

    failures = verify_repository(tmp_path)

    assert any(
        "is not valid YAML" in failure for failure in _pinning_failures(failures)
    )
    assert "okr-database-url-secret-value" not in "\n".join(failures)
