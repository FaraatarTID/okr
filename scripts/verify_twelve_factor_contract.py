"""Verify repository evidence for the Twelve-Factor runtime contract.

This is intentionally a static, secret-safe check. It does not load dotenv
files, invoke Compose, contact a registry, or print manifest contents.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_SENSITIVE_NAMES = re.compile(
    r"(?:PASSWORD|TOKEN|SECRET|API_KEY|DATABASE_URL|PRIVATE_KEY)", re.IGNORECASE
)
_ENV_ASSIGNMENT = re.compile(r"^\s*([^#\s=]+)\s*=\s*(.*)$")


def _is_secret_key(name: str) -> bool:
    normalized = name.upper()
    if "ENFORCE" in normalized:
        return False
    return (
        normalized.endswith(("_PASSWORD", "_TOKEN", "_SECRET", "_API_KEY"))
        or normalized.endswith("DATABASE_URL")
    )


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
    missing = [f"{manifest} -> {lockfile}" for manifest, lockfile in required if not _exists(root, manifest) or not _exists(root, lockfile)]
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
        if _SENSITIVE_NAMES.search(line) and "${" not in line and not line.lstrip().startswith("#"):
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
    if not re.search(r"(?:@sha256:|digest|RELEASE_SHA|commit_sha)", combined, re.IGNORECASE):
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
        renderer = _read(root, "scripts/render_k8s_release.py")
        if renderer is None or "64" not in renderer or "REPLACE_WITH_RELEASE_DIGEST" not in renderer:
            return "Kubernetes release renderer is missing digest validation"
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
    if compose is None or "ports:" not in compose or not re.search(r"ports:\s*\n(?:\s+-[^\n]+\n)+", compose):
        failures.append("port binding is not declared in Compose")
    if any(content is None or not re.search(r"^EXPOSE\s+\d+", content, re.MULTILINE) for content in (backend, bff, web)):
        failures.append("container port exposure is missing from a service Dockerfile")
    if compose is None or "healthcheck:" not in compose:
        failures.append("Compose healthchecks are missing")
    web_match = re.search(r"^  spa-web:\s*$([\s\S]*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)", compose or "", re.MULTILINE)
    if web_match and not re.search(
        r"\$\{SPA_WEB_HOST_PORT[^}]*\}:\$\{SPA_WEB_PORT",
        web_match.group(1),
    ):
        failures.append("spa-web port mapping does not target its configured container port")
    if backend is None or "HEALTHCHECK" not in backend:
        failures.append("backend Dockerfile healthcheck is missing")
    return failures


def _check_admin_processes(root: Path) -> str | None:
    documentation = "\n".join(
        content
        for path in ("README.md", "docs/saas/prerelease-runbook.md", "deploy/darkube/prerelease/README.md")
        if (content := _read(root, path)) is not None
    )
    if not re.search(r"\b(?:alembic\s+upgrade\s+head|docker\s+compose\s+run|docker-compose\s+run)\b", documentation, re.IGNORECASE):
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
    failures.extend(f"Twelve-Factor runtime contract: {failure}" for failure in _check_ports_and_healthchecks(root))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
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
