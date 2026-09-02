from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


SENSITIVE_KEY_RE = re.compile(
    r"""
    (?:
        ["'](?P<key>password|new_password|bootstrap_admin_password)["']\s*:\s*
        ["'](?P<value>[^"']+)["']
        |
        (?<!def\s)(?<!class\s)\b(?P<assign_key>password|new_password|bootstrap_admin_password)\b\s*=\s*
        ["'](?P<assign_value>[^"']+)["']
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

ALLOWLIST_SUBSTRINGS = (
    "weakpass",
    "please-change",
    "placeholder",
    "CHANGE_ME_STRONG_BOOTSTRAP_PASSWORD",
    "unit-test",
    "e2e-atlas-password",
    "test-signing-secret",
    "super-secret-signing-key",
    "runtime-smoke",
    "smoke-secret",
    "session-secret",
    "signing-secret",
)


def _is_allowed_key(key: str, value: str, line: str) -> bool:
    lowered = value.lower()
    if "test_password(" in line:
        return True
    if "change" in key:
        return True
    if re.search(r"\bnew_password\b\s*=", line):
        return True
    if "hash_password" in line:
        return True
    if any(token in lowered for token in ALLOWLIST_SUBSTRINGS):
        return True
    return False


def _scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, raw_line in enumerate(text, start=1):
        line = raw_line.strip()
        if "# secret-hygiene: ignore" in line:
            continue
        match = SENSITIVE_KEY_RE.search(raw_line)
        if not match:
            continue
        key = match.group("key") or match.group("assign_key")
        value = match.group("value") or match.group("assign_value")
        if _is_allowed_key(key, value, line):
            continue
        findings.append(f"{path}:{i}:{line}")
    return findings


def main() -> int:
    target_files = []
    target_patterns = ("tests", "scripts", ".github")
    for pattern in target_patterns:
        scan_root = ROOT / pattern
        for path in scan_root.rglob("*.py"):
            if any(part.startswith(".") for part in path.parts):
                continue
            if "venv" in path.parts or ".venv" in path.parts or ".git" in path.parts:
                continue
            target_files.append(path)

    issues: list[str] = []
    for file in target_files:
        issues.extend(_scan_file(file))

    if issues:
        print("[SECRET-HYGIENE] Disallowed inline test/fixture credentials detected:")
        for item in issues:
            print(f" - {item}")
        print(
            "Remediation: replace hardcoded credential values with "
            "tests._test_credentials.test_password(...) or environment-driven fixtures."
        )
        return 1

    print("[SECRET-HYGIENE] No inline secret-likely credentials detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
