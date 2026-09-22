from __future__ import annotations

from pathlib import Path

from scripts.verify_twelve_factor_contract import (
    _image_digests,
    _run_release_renderer,
    verify_repository,
)


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

    Each carries the unresolved digest placeholder, as the shipped manifests do, so a
    renderer that never substitutes anything cannot pass by accident.
    """
    for name in (
        "deployment-backend-api.yaml",
        "deployment-backend-worker.yaml",
    ):
        _write(
            root,
            f"deploy/k8s/{name}",
            "kind: Deployment\n"
            "spec:\n"
            "  template:\n"
            "    spec:\n"
            "      containers:\n"
            "        - image: ghcr.io/example/okr-backend@sha256:"
            "REPLACE_WITH_RELEASE_DIGEST\n",
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
    # whole-file substring search would have accepted this manifest.
    assert requested in rendered
    assert requested not in _image_digests(rendered)

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
