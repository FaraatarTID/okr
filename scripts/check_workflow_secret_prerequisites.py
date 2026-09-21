"""Fail a pull request when a workflow needs a secret nobody has provisioned.

Motivation: from `62774ef` onward `publish-ghcr.yml` required
`OKR_RELEASE_MANIFEST_ATTESTATION_SECRET`, while the repository had no such secret,
so `scripts/create_release_manifest.py --require-attestation` failed closed on every
push to `main`. That workflow triggers only on push, so no pull request could ever
have caught it, and the test that covered the wiring asserted the secret was
*referenced* rather than that it *existed*. The result was two consecutive red merges
of `main` before anyone noticed.

What this checker can and cannot do, stated plainly because the difference matters:

- It **cannot** read repository secret metadata. Confirming that a secret exists
  needs `admin:repo` scope, which CI does not and should not hold. So it does not
  claim to verify provisioning, and passing it is not evidence that a workflow will
  run.
- It **can** make the requirement explicit at pull-request time: every `secrets.X` a
  workflow references must be declared in `docs/deploy/required-secrets.json`, and a
  secret referenced by a workflow that does not trigger on `pull_request` must be
  marked `"post_merge_only": true`. That forces the reviewer to confront "this
  dependency cannot be exercised before merge" at review time rather than after.

Passing this gate means "the prerequisites are declared and reviewed", never "the
prerequisites are satisfied".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
DECLARATION = ROOT / "docs" / "deploy" / "required-secrets.json"

# Provided by Actions itself on every run; never provisioned by an operator.
AUTOMATIC_SECRETS = frozenset({"GITHUB_TOKEN"})

_SECRET_RE = re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)")


class SecretUsage(TypedDict):
    """Which workflows reference a secret, and whether any can run on a pull request."""

    workflows: list[str]
    all_post_merge_only: bool


def _without_comments(text: str) -> str:
    """Drop `#` comments so a commented-out reference is not counted."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def referenced_secrets(text: str) -> set[str]:
    """Secret names a workflow references, excluding automatic ones."""
    found = set(_SECRET_RE.findall(_without_comments(text)))
    return found - AUTOMATIC_SECRETS


def triggers_on_pull_request(text: str) -> bool:
    """Whether the workflow's `on:` block includes `pull_request`.

    Parsed by indentation rather than with a YAML library, because PyYAML is
    installed in this environment but is not a declared dependency and this script
    must not introduce one.
    """
    lines = _without_comments(text).splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("on:"):
            continue
        if stripped != "on:":
            # Inline form, e.g. `on: [push, pull_request]`.
            return "pull_request" in stripped
        for following in lines[index + 1 :]:
            if not following.strip():
                continue
            if not following.startswith((" ", "\t")):
                break
            if following.strip().startswith("pull_request"):
                return True
        return False
    return False


def scan(workflows_dir: Path) -> dict[str, SecretUsage]:
    """Map each secret name to the workflows referencing it and their triggers."""
    result: dict[str, SecretUsage] = {}
    for path in sorted(workflows_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        pr_checkable = triggers_on_pull_request(text)
        for name in referenced_secrets(text):
            entry = result.setdefault(
                name, SecretUsage(workflows=[], all_post_merge_only=True)
            )
            entry["workflows"].append(path.name)
            if pr_checkable:
                entry["all_post_merge_only"] = False
    return result


def load_declaration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    declared: dict[str, Any] = {}
    for item in payload.get("secrets", []):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        declared[name] = item
    return declared


def problems(derived: dict[str, SecretUsage], declared: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for name in sorted(set(derived) - set(declared)):
        entry = derived[name]
        workflows = ", ".join(entry["workflows"])
        findings.append(
            f"{name} is referenced by {workflows} but is not declared in "
            f"{DECLARATION.relative_to(ROOT)}. A workflow cannot run until an "
            "operator provisions it; declare it so a reviewer sees that before merge."
        )
    for name in sorted(set(declared) - set(derived)):
        findings.append(
            f"{name} is declared in {DECLARATION.relative_to(ROOT)} but no workflow "
            "references it any more; remove the stale declaration."
        )
    for name in sorted(set(derived) & set(declared)):
        entry = derived[name]
        if entry["all_post_merge_only"] and not declared[name].get("post_merge_only"):
            workflows = ", ".join(entry["workflows"])
            findings.append(
                f"{name} is referenced only by workflows that do not trigger on "
                f"pull_request ({workflows}), so nothing can exercise it before "
                'merge. Mark it "post_merge_only": true and state the remediation.'
            )
        if not entry["all_post_merge_only"] and declared[name].get("post_merge_only"):
            findings.append(
                f'{name} is marked "post_merge_only" but a workflow referencing it '
                "does trigger on pull_request; the marker is now inaccurate."
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-derived",
        action="store_true",
        help="Print the scanned state as JSON and exit, for refreshing the declaration.",
    )
    args = parser.parse_args(argv)

    derived = scan(WORKFLOWS_DIR)
    if args.print_derived:
        print(json.dumps(derived, indent=2, sort_keys=True))
        return 0

    if not DECLARATION.exists():
        print(f"[SECRET-PREREQUISITES] {DECLARATION} is missing.", file=sys.stderr)
        return 1

    findings = problems(derived, load_declaration(DECLARATION))
    if findings:
        print("[SECRET-PREREQUISITES] Workflow secret prerequisites are undeclared:")
        for finding in findings:
            print(f"  - {finding}")
        print(
            "\nThis gate does not prove a secret exists; it proves the requirement is "
            "declared and reviewable. Provisioning is an operator action."
        )
        return 1

    post_merge = sorted(
        name for name, entry in derived.items() if entry["all_post_merge_only"]
    )
    print(
        f"Workflow secret prerequisites declared: {len(derived)} secret(s) across "
        f"{len(list(WORKFLOWS_DIR.glob('*.yml')))} workflow(s)."
    )
    if post_merge:
        print(
            "  Post-merge only, so unverifiable by pull-request CI: "
            + ", ".join(post_merge)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
