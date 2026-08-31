#!/usr/bin/env python3
"""Validate docs navigation links to README documentation HQ."""

from __future__ import annotations

import re
import subprocess
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_README = (ROOT / "README.md").resolve()
HQ_LINK_RE = re.compile(
    r"^Documentation HQ:\s*\[README\]\((?P<link>[^)]+)\)\s*$",
    re.MULTILINE,
)


def _tracked_markdown_files() -> list[Path]:
    """Return tracked markdown files in the repository."""
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "*.md"],
            cwd=ROOT,
            text=True,
        )
        files = []
        for rel in output.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            path = (ROOT / rel).resolve()
            # Skip tracked docs that are currently deleted in the working tree.
            # This keeps local checks stable before `git add -A`.
            if path.exists():
                files.append(path)
        return files
    except Exception:
        # Fallback if git is unavailable.
        return sorted(p.resolve() for p in ROOT.rglob("*.md") if ".git" not in p.parts)


def _clean_link_target(link: str) -> str:
    """Strip optional anchor/query suffixes from markdown links."""
    return link.split("#", 1)[0].split("?", 1)[0].strip()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _expected_readme_link(doc_path: Path) -> str:
    return os.path.relpath(ROOT_README, doc_path.parent).replace("\\", "/")


def _validate_hq_targets(readme_text: str) -> list[str]:
    """Validate local links listed inside the README Documentation HQ section."""
    start_marker = "## Documentation HQ"
    end_marker = "## Deployment Intent"
    start = readme_text.find(start_marker)
    if start < 0:
        return []
    end = readme_text.find(end_marker, start + len(start_marker))
    section = readme_text[start:] if end < 0 else readme_text[start:end]

    errors: list[str] = []
    link_re = re.compile(r"\[[^\]]+\]\((?P<link>[^)]+)\)")
    for match in link_re.finditer(section):
        link = match.group("link").strip()
        target = _clean_link_target(link)
        if not target or target.startswith(("http://", "https://", "#")):
            continue
        resolved = (ROOT_README.parent / target).resolve()
        if not resolved.exists():
            errors.append(
                f"README.md Documentation HQ link '{link}' does not resolve "
                f"to an existing path ({_display_path(resolved)})."
            )
    return errors


def validate() -> int:
    errors: list[str] = []
    files = _tracked_markdown_files()

    if not ROOT_README.exists():
        print("ERROR: README.md not found at repository root.")
        return 1

    readme_text = ROOT_README.read_text(encoding="utf-8")
    if "## Documentation HQ" not in readme_text:
        errors.append("README.md is missing the '## Documentation HQ' section.")
    errors.extend(_validate_hq_targets(readme_text))

    for doc in files:
        if doc == ROOT_README:
            continue

        try:
            text = doc.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{_display_path(doc)}: not valid UTF-8 text.")
            continue

        match = HQ_LINK_RE.search(text)
        if not match:
            errors.append(
                f"{_display_path(doc)}: missing "
                "'Documentation HQ: [README](...)' backlink."
            )
            continue

        link = match.group("link").strip()
        target = _clean_link_target(link)
        if not target:
            errors.append(f"{_display_path(doc)}: backlink target is empty.")
            continue
        if target.startswith(("http://", "https://")):
            errors.append(
                f"{_display_path(doc)}: backlink must be relative, got '{link}'."
            )
            continue

        resolved_target = (doc.parent / target).resolve()
        if resolved_target != ROOT_README:
            expected = _expected_readme_link(doc)
            errors.append(
                f"{_display_path(doc)}: backlink points to '{link}' "
                f"(resolves to {_display_path(resolved_target)}), "
                f"expected '{expected}'."
            )

    if errors:
        print("Documentation HQ link check failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print(f"Documentation HQ link check passed ({len(files)} markdown files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
