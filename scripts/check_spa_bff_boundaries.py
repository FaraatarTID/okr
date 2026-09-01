#!/usr/bin/env python3
"""Check that spa-bff TypeScript imports stay inside the BFF boundary.

The checker intentionally uses only the Python standard library so it can run
before Node dependencies are installed. It scans production TypeScript under
``spa-bff/src`` and reports the source location and rule for every violation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BFF_DIR = ROOT_DIR / "spa-bff"

# These are packages that provide a direct database connection or database ORM.
# The BFF may call the backend over HTTP, but must not own persistence access.
DATABASE_PACKAGES = frozenset(
    {
        "@prisma/client",
        "@supabase/supabase-js",
        "better-sqlite3",
        "drizzle-orm",
        "ioredis",
        "knex",
        "mongodb",
        "mongoose",
        "mysql",
        "mysql2",
        "pg",
        "pg-promise",
        "postgres",
        "postgresjs",
        "redis",
        "sequelize",
        "sqlite3",
        "typeorm",
    }
)

BACKEND_MODULES = frozenset(
    {
        "app",
        "backend_app",
        "src",
    }
)
FORBIDDEN_RUNTIME_PACKAGES = DATABASE_PACKAGES | BACKEND_MODULES | frozenset(
    {"next", "react", "react-dom", "spa-web", "okr-platform-workspace"}
)
OPENAPI_TOOLING_PACKAGES = frozenset({"openapi-typescript"})

IMPORT_RE = re.compile(
    r"(?m)^\s*(?P<statement>import\b[^;\n]*?from\s+|export\b[^;\n]*?from\s+|import\s*)"
    r"[\"'](?P<module>[^\"']+)[\"']"
)
COMMENT_RE = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/")


@dataclass(frozen=True)
class ImportReference:
    module: str
    line: int
    statement: str


def _strip_comments(source: str) -> str:
    """Remove comments while preserving newlines for stable line reporting."""

    def replace(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return COMMENT_RE.sub(replace, source)


def _imports(source: str) -> list[ImportReference]:
    clean_source = _strip_comments(source)
    references: list[ImportReference] = []
    for match in IMPORT_RE.finditer(clean_source):
        references.append(
            ImportReference(
                module=match.group("module"),
                line=clean_source.count("\n", 0, match.start()) + 1,
                statement=match.group("statement").strip(),
            )
        )
    # CommonJS is not currently used by the BFF, but checking it prevents a
    # boundary bypass if a file is converted from ESM later.
    require_re = re.compile(r"\brequire\(\s*[\"']([^\"']+)[\"']\s*\)")
    for match in require_re.finditer(clean_source):
        references.append(
            ImportReference(
                module=match.group(1),
                line=clean_source.count("\n", 0, match.start()) + 1,
                statement="require",
            )
        )
    dynamic_re = re.compile(r"\bimport\(\s*[\"']([^\"']+)[\"']\s*\)")
    for match in dynamic_re.finditer(clean_source):
        references.append(
            ImportReference(
                module=match.group(1),
                line=clean_source.count("\n", 0, match.start()) + 1,
                statement="dynamic import",
            )
        )
    return references


def _package_name(module: str) -> str:
    if module.startswith("@"):
        return "/".join(module.split("/")[:2])
    return module.split("/", 1)[0]


def _relative_target(importer: Path, module: str) -> Path | None:
    if not module.startswith("."):
        return None
    return (importer.parent / module).resolve()


def _is_generated_api_import(importer: Path, module: str, bff_dir: Path) -> bool:
    target = _relative_target(importer, module)
    if target is None:
        return False
    generated_dir = (bff_dir / "src" / "generated").resolve()
    try:
        target.relative_to(generated_dir)
    except ValueError:
        return False
    return True


def _violations(
    importer: Path,
    reference: ImportReference,
    root: Path,
    bff_dir: Path,
) -> list[str]:
    module = reference.module
    relative_path = importer.relative_to(root).as_posix()
    location = f"{relative_path}:{reference.line}"
    errors: list[str] = []

    if _is_generated_api_import(importer, module, bff_dir):
        return errors

    target = _relative_target(importer, module)
    if target is not None:
        try:
            target_relative = target.relative_to(root).as_posix()
        except ValueError:
            errors.append(
                f"{location}: forbidden import '{module}': relative import leaves the repository"
            )
            return errors

        top_level = target_relative.split("/", 1)[0]
        if top_level == "spa-web":
            errors.append(
                f"{location}: forbidden import '{module}': spa-bff must not import spa-web implementation modules"
            )
        elif top_level in {"backend_app", "src"} or target.suffix == ".py":
            errors.append(
                f"{location}: forbidden import '{module}': spa-bff must not import Python/backend internals"
            )
        return errors

    package = _package_name(module)
    if package in DATABASE_PACKAGES:
        errors.append(
            f"{location}: forbidden import '{module}': spa-bff must not import direct database clients"
        )
    elif package in BACKEND_MODULES or module.startswith(("backend_app/", "src/")):
        errors.append(
            f"{location}: forbidden import '{module}': spa-bff must not import Python/backend internals"
        )
    return errors


def _manifest_violations(manifest_path: Path) -> list[str]:
    """Check that the BFF manifest exposes no cross-boundary runtime packages."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime: dict[str, str] = {}
    for section in ("dependencies", "optionalDependencies"):
        runtime.update(manifest.get(section, {}))

    errors: list[str] = []
    for package in sorted(set(runtime) & FORBIDDEN_RUNTIME_PACKAGES):
        errors.append(
            f"{manifest_path}: forbidden runtime dependency '{package}': "
            "spa-bff must not depend on backend, spa-web, or persistence packages"
        )
    misplaced_tools = sorted(set(runtime) & OPENAPI_TOOLING_PACKAGES)
    for package in misplaced_tools:
        errors.append(
            f"{manifest_path}: '{package}' must be a development dependency, "
            "not a runtime dependency"
        )
    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bff-dir",
        type=Path,
        default=DEFAULT_BFF_DIR,
        help="spa-bff directory (default: repository spa-bff)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    bff_dir = args.bff_dir.resolve()
    source_dir = bff_dir / "src"
    files = sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx"}
    )
    errors: list[str] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path}: cannot read TypeScript source: {exc}")
            continue
        for reference in _imports(source):
            errors.extend(_violations(path, reference, ROOT_DIR, bff_dir))

    manifest_path = bff_dir / "package.json"
    try:
        errors.extend(_manifest_violations(manifest_path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{manifest_path}: cannot validate package manifest: {exc}")

    if errors:
        print("spa-bff TypeScript boundary check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1

    print(f"spa-bff TypeScript boundary check passed ({len(files)} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
