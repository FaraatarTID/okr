"""Verify repository evidence for the Twelve-Factor runtime contract.

This is intentionally a static, secret-safe check. It does not load dotenv
files, invoke Compose, contact a registry, or print manifest contents.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple


_SENSITIVE_NAMES = re.compile(
    r"(?:PASSWORD|TOKEN|SECRET|API_KEY|DATABASE_URL|PRIVATE_KEY)", re.IGNORECASE
)
_ENV_ASSIGNMENT = re.compile(r"^\s*([^#\s=]+)\s*=\s*(.*)$")

_RENDERER_RELATIVE = "scripts/render_k8s_release.py"
_RENDER_TIMEOUT_SECONDS = 120.0
# Distinct digests so that substituting one input into the other manifest is visible.
_VALID_DIGESTS = {"api_digest": "1" * 64, "worker_digest": "2" * 64}
_MANIFEST_FOR_LABEL = {
    "api_digest": "deployment-backend-api.yaml",
    "worker_digest": "deployment-backend-worker.yaml",
}
_INVALID_DIGEST = "not-a-sha256-digest"
# Matched against RENDERED OUTPUT only. The check never reads the renderer's source, so a
# module that merely mentions the right strings cannot satisfy it.
_PLACEHOLDER = "REPLACE_WITH_RELEASE_DIGEST"


def _is_secret_key(name: str) -> bool:
    normalized = name.upper()
    if "ENFORCE" in normalized:
        return False
    return normalized.endswith(
        ("_PASSWORD", "_TOKEN", "_SECRET", "_API_KEY")
    ) or normalized.endswith("DATABASE_URL")


def _read(root: Path, relative: str) -> str | None:
    path = root / relative
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def _check_dependencies(root: Path) -> str | None:
    required = (
        ("pyproject.toml", "uv.lock"),
        ("package.json", "package-lock.json"),
        ("spa-bff/package.json", "spa-bff/package-lock.json"),
        ("spa-web/package.json", "spa-web/package-lock.json"),
    )
    missing = [
        f"{manifest} -> {lockfile}"
        for manifest, lockfile in required
        if not _exists(root, manifest) or not _exists(root, lockfile)
    ]
    if missing:
        return "dependency lockfiles are missing for one or more manifests"
    return None


def _check_config(root: Path) -> str | None:
    templates = ("deploy/docker/.env.example", "deploy/docker/.env.saas.example")
    if any(not _exists(root, template) for template in templates):
        return "environment configuration templates are missing"
    compose = _read(root, "deploy/docker/docker-compose.yml")
    if compose is None:
        return "Compose configuration is missing"
    for line in compose.splitlines():
        if (
            _SENSITIVE_NAMES.search(line)
            and "${" not in line
            and not line.lstrip().startswith("#")
        ):
            return "Compose contains a non-environment-driven sensitive setting"
    for template in templates:
        content = _read(root, template) or ""
        if any(
            (match := _ENV_ASSIGNMENT.match(line))
            and _is_secret_key(match.group(1))
            and match.group(2).strip()
            and "CHANGE_ME" not in match.group(2)
            and "${" not in match.group(2)
            for line in content.splitlines()
        ):
            return "environment templates contain a literal secret-like value"
    return None


# The digest must appear in a container image value, not merely somewhere in the file. A
# digest quoted in a comment or parked in an unrelated field pins no image, so searching
# the whole manifest for that hex string would accept a manifest that deploys nothing the
# caller asked for.
_IMAGE_VALUE = re.compile(r"^\s*(?:-\s+)?image:\s*(\S+)\s*$", re.MULTILINE)
_IMAGE_DIGEST = re.compile(r"@sha256:([0-9a-fA-F]{64})$")


def _image_digests(rendered: str) -> list[str]:
    """Return the digests that appear inside an ``image:`` value, and only those."""

    found: list[str] = []
    for match in _IMAGE_VALUE.finditer(rendered):
        pinned = _IMAGE_DIGEST.search(match.group(1))
        if pinned:
            found.append(pinned.group(1).lower())
    return found


class _RenderOutcome(NamedTuple):
    """One bounded renderer invocation.

    ``executed`` is False when the interpreter did not run the renderer to completion,
    which includes a timeout. That case must never be read as "the renderer rejected this
    input", because an unrelated execution failure would then masquerade as a successful
    rejection of an invalid digest.
    """

    executed: bool
    returncode: int
    output: str


def _summarise(output: str, limit: int = 200) -> str:
    """Reduce renderer output to one bounded line, without echoing manifest contents."""

    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped[:limit]
    return "no output"


def _run_release_renderer(
    root: Path, *, api_digest: str, worker_digest: str, output_dir: Path
) -> _RenderOutcome:
    """Render release manifests in a bounded subprocess and report what happened.

    This executes trusted repository code with the running interpreter. It is NOT a
    security sandbox: the renderer runs with the permissions of this check process and can
    read and write whatever it can, so it must never be pointed at untrusted code. The
    subprocess exists to observe the renderer's real behaviour - and to keep import-time
    side effects out of this process - not to contain it.
    """

    command = (
        sys.executable,
        str(root / _RENDERER_RELATIVE),
        "--api-digest",
        api_digest,
        "--worker-digest",
        worker_digest,
        "--output-dir",
        str(output_dir),
    )
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _RenderOutcome(False, 124, "renderer timed out")
    except OSError as exc:
        return _RenderOutcome(False, 125, f"renderer could not be started: {exc}")
    return _RenderOutcome(
        True, completed.returncode, completed.stdout + completed.stderr
    )


def _check_release_renderer(root: Path) -> str | None:
    """Exercise the release renderer and judge it by what it does, not what it declares.

    The previous check read the renderer's source and searched it for the substrings "64"
    and "REPLACE_WITH_RELEASE_DIGEST". A module holding those two constants and rendering
    nothing satisfied it, so it certified a renderer that could neither validate a digest
    nor emit a manifest. Every judgement below comes from running the renderer and
    inspecting the files it produced, so comments and string constants cannot affect the
    outcome.
    """

    if not (root / _RENDERER_RELATIVE).is_file():
        return "Kubernetes release renderer is missing digest validation"

    with tempfile.TemporaryDirectory(prefix="okr-release-render-") as directory:
        workspace = Path(directory)

        valid = _run_release_renderer(
            root,
            api_digest=_VALID_DIGESTS["api_digest"],
            worker_digest=_VALID_DIGESTS["worker_digest"],
            output_dir=workspace / "valid",
        )
        if not valid.executed:
            return (
                "Kubernetes release renderer could not be executed, so its digest "
                f"validation is unverified: {_summarise(valid.output)}"
            )
        if valid.returncode != 0:
            return (
                "Kubernetes release renderer rejected a valid pair of digests, so it "
                f"does not implement digest validation: {_summarise(valid.output)}"
            )
        for label, digest in _VALID_DIGESTS.items():
            filename = _MANIFEST_FOR_LABEL[label]
            rendered = _read(workspace / "valid", filename)
            if rendered is None:
                return (
                    f"Kubernetes release renderer did not produce {filename}, so it is "
                    "not a functioning release renderer"
                )
            if _PLACEHOLDER.lower() in rendered.lower():
                return (
                    f"rendered {filename} still contains an unresolved digest "
                    "placeholder, so the renderer can emit an unrenderable manifest"
                )
            if digest not in _image_digests(rendered):
                return (
                    f"rendered {filename} does not pin the validated digest in a "
                    "container image value, so the manifest does not deploy the digest "
                    "it was given"
                )

        # Each invalid input is checked with the other input valid, so a renderer that
        # validates only one of the two labels is reported rather than passing on the
        # strength of the other.
        for label in _VALID_DIGESTS:
            inputs = dict(_VALID_DIGESTS)
            inputs[label] = _INVALID_DIGEST
            rejected = _run_release_renderer(
                root,
                api_digest=inputs["api_digest"],
                worker_digest=inputs["worker_digest"],
                output_dir=workspace / f"invalid-{label}",
            )
            if not rejected.executed:
                return (
                    f"Kubernetes release renderer could not be executed while checking "
                    f"{label}, so digest validation is unverified: "
                    f"{_summarise(rejected.output)}"
                )
            if rejected.returncode == 0:
                return (
                    f"Kubernetes release renderer accepted an invalid {label}, so it "
                    "does not enforce digest validation"
                )
            if label not in rejected.output:
                # A non-zero exit for any other reason - a crash, a missing file, a syntax
                # error - is not evidence that the digest was rejected. Requiring the
                # failure to name the offending input is what stops an unrelated execution
                # failure from masquerading as a successful rejection.
                return (
                    f"Kubernetes release renderer failed while checking {label} without "
                    "naming it, so the rejection cannot be attributed to digest "
                    f"validation: {_summarise(rejected.output)}"
                )
    return None


def _check_immutable_images(root: Path) -> str | None:
    deployment_files = tuple(
        path
        for path in (
            ".github/workflows/promote-production.yml",
            ".github/workflows/rollback-production.yml",
            ".github/workflows/docker-deploy.yml",
        )
        if _exists(root, path)
    )
    if not deployment_files:
        return "promotion configuration is missing"
    combined = "\n".join(_read(root, path) or "" for path in deployment_files)
    if ":latest" in combined or "up -d --build" in combined:
        return "deployment configuration permits mutable images or host-side rebuilds"
    if not re.search(
        r"(?:@sha256:|digest|RELEASE_SHA|commit_sha)", combined, re.IGNORECASE
    ):
        return "promotion configuration lacks immutable image references"
    k8s_files = tuple(
        path
        for path in (
            "deploy/k8s/deployment-backend-api.yaml",
            "deploy/k8s/deployment-backend-worker.yaml",
        )
        if _exists(root, path)
    )
    if k8s_files:
        renderer_failure = _check_release_renderer(root)
        if renderer_failure:
            return renderer_failure
    release_overlay = _read(root, "deploy/docker/docker-compose.release.yml")
    if release_overlay is None:
        return "release Compose overlay is missing"
    required_inputs = (
        "OKR_RELEASE_BACKEND_IMAGE",
        "OKR_RELEASE_BFF_IMAGE",
        "OKR_RELEASE_WEB_IMAGE",
    )
    if any(f"{name}:?" not in release_overlay for name in required_inputs):
        return "release Compose overlay does not require all release image inputs"
    deploy_workflow = _read(root, ".github/workflows/docker-deploy.yml")
    if deploy_workflow is None or "sha256:[0-9a-fA-F]{64}" not in deploy_workflow:
        return "release workflow does not enforce sha256 image digest syntax"
    return None


def _check_ports_and_healthchecks(root: Path) -> list[str]:
    failures: list[str] = []
    compose = _read(root, "deploy/docker/docker-compose.yml")
    backend = _read(root, "deploy/docker/Dockerfile")
    bff = _read(root, "spa-bff/Dockerfile")
    web = _read(root, "spa-web/Dockerfile")
    if (
        compose is None
        or "ports:" not in compose
        or not re.search(r"ports:\s*\n(?:\s+-[^\n]+\n)+", compose)
    ):
        failures.append("port binding is not declared in Compose")
    if any(
        content is None or not re.search(r"^EXPOSE\s+\d+", content, re.MULTILINE)
        for content in (backend, bff, web)
    ):
        failures.append("container port exposure is missing from a service Dockerfile")
    if compose is None or "healthcheck:" not in compose:
        failures.append("Compose healthchecks are missing")
    web_match = re.search(
        r"^  spa-web:\s*$([\s\S]*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)",
        compose or "",
        re.MULTILINE,
    )
    if web_match and not re.search(
        r"\$\{SPA_WEB_HOST_PORT[^}]*\}:\$\{SPA_WEB_PORT",
        web_match.group(1),
    ):
        failures.append(
            "spa-web port mapping does not target its configured container port"
        )
    if backend is None or "HEALTHCHECK" not in backend:
        failures.append("backend Dockerfile healthcheck is missing")
    return failures


def _check_admin_processes(root: Path) -> str | None:
    documentation = "\n".join(
        content
        for path in (
            "README.md",
            "docs/saas/prerelease-runbook.md",
            "deploy/darkube/prerelease/README.md",
        )
        if (content := _read(root, path)) is not None
    )
    if not re.search(
        r"\b(?:alembic\s+upgrade\s+head|docker\s+compose\s+run|docker-compose\s+run)\b",
        documentation,
        re.IGNORECASE,
    ):
        return "one-off admin command documentation is missing"
    return None


def verify_repository(root: Path) -> list[str]:
    """Return secret-safe contract failures for *root*."""

    failures: list[str] = []
    checks: tuple[tuple[str, str | None], ...] = (
        ("dependency lockfiles", _check_dependencies(root)),
        ("environment-driven configuration", _check_config(root)),
        ("immutable image references", _check_immutable_images(root)),
        ("one-off admin command", _check_admin_processes(root)),
    )
    failures.extend(f"{name}: {failure}" for name, failure in checks if failure)
    failures.extend(
        f"Twelve-Factor runtime contract: {failure}"
        for failure in _check_ports_and_healthchecks(root)
    )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args(argv)
    failures = verify_repository(args.root.resolve())
    if failures:
        print("[TWELVE-FACTOR] Contract failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[TWELVE-FACTOR] Repository contract passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
