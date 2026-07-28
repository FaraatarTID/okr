#!/usr/bin/env python3
"""Verify Playwright SPA e2e prerequisites in a deterministic way."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""


def _run_capture(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
        )
    except FileNotFoundError:
        return 127, ""
    output = ""
    if proc.stdout:
        output = proc.stdout.strip()
    if proc.stderr:
        if output:
            output = f"{output}\n{proc.stderr.strip()}"
        else:
            output = proc.stderr.strip()
    return proc.returncode, output


def _check_binary(name: str) -> CheckResult:
    if shutil.which(name):
        return CheckResult(name=f"{name} present", passed=True)
    return CheckResult(
        name=f"{name} present",
        passed=False,
        details=(
            f"'{name}' was not found on PATH. "
            f"Install Node.js LTS to provide {name} and reopen your shell."
        ),
    )


def _check_project_scripts(project_dir: Path, label: str) -> CheckResult:
    package_json = project_dir / "package.json"
    if not package_json.exists():
        return CheckResult(
            name=f"{label}: package.json",
            passed=False,
            details=f"Missing {package_json.as_posix()}",
        )

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult(
            name=f"{label}: package.json",
            passed=False,
            details=f"Cannot parse {package_json.as_posix()}: {exc}",
        )

    scripts = data.get("scripts", {})
    if "dev" not in scripts:
        return CheckResult(
            name=f"{label}: npm script dev",
            passed=False,
            details=f"{package_json.as_posix()} missing scripts.dev",
        )

    return CheckResult(name=f"{label}: scripts.dev", passed=True)


def _check_node_modules(project_dir: Path, label: str) -> CheckResult:
    node_modules = project_dir / "node_modules"
    if not node_modules.exists():
        return CheckResult(
            name=f"{label}: node_modules",
            passed=False,
            details=f"{node_modules.as_posix()} not found. Run: (cd {project_dir.name} && npm install)",
        )
    return CheckResult(name=f"{label}: node_modules", passed=True)


def _check_playwright_command(project_dir: Path, label: str) -> CheckResult:
    if not (project_dir / "node_modules" / ".bin" / "playwright").exists():
        return CheckResult(
            name=f"{label}: playwright CLI",
            passed=False,
            details=(
                f"Playwright binary not found under {project_dir.as_posix()}/node_modules/.bin. "
                f"Run: (cd {project_dir.name} && npm install && npx playwright install chromium)"
            ),
        )
    code, output = _run_capture(["npx", "playwright", "install", "--dry-run"], project_dir)
    if code != 0:
        return CheckResult(
            name=f"{label}: playwright CLI",
            passed=False,
            details=f"Playwright command check failed ({code}): {output}",
        )
    return CheckResult(
        name=f"{label}: playwright CLI",
        passed=True,
        details=(output or "Playwright binary available."),
    )


def verify(project_root: Path) -> int:
    checks: list[CheckResult] = [
        _check_binary("node"),
        _check_binary("npm"),
        _check_binary("npx"),
        _check_project_scripts(project_root / "spa-web", "spa-web"),
        _check_project_scripts(project_root / "spa-bff", "spa-bff"),
        _check_node_modules(project_root / "spa-web", "spa-web"),
        _check_node_modules(project_root / "spa-bff", "spa-bff"),
        _check_playwright_command(project_root / "spa-web", "spa-web"),
        _check_playwright_command(project_root / "spa-bff", "spa-bff"),
    ]

    failed: list[CheckResult] = [check for check in checks if not check.passed]
    for check in checks:
        status = "[PASS]" if check.passed else "[FAIL]"
        line = f"{status} {check.name}"
        if check.details:
            line += f" :: {check.details}"
        print(line)

    if failed:
        print("\nSetup guidance:")
        print("- cd spa-web && npm install")
        print("- cd spa-bff && npm install")
        print("- npm install -g @playwright/test (if preferred) OR npm install in each project")
        print("- npx playwright install chromium")
        return 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Playwright SPA e2e environment.")
    parser.add_argument(
        "--root",
        default=str(PROJECT_ROOT),
        help="Project root to verify (default: repository root).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()
    return verify(root)


if __name__ == "__main__":
    raise SystemExit(main())
