#!/usr/bin/env python3
"""Detect likely hardcoded credentials in test fixture payloads and config snippets."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecretFinding:
    file: Path
    line: int
    symbol: str
    value: str


SENSITIVE_KEYS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
    "auth_token",
)


def _is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    if "seed" in lowered:
        return False
    if "default" in lowered:
        return False
    return any(key in lowered for key in SENSITIVE_KEYS)


def _looks_like_literal_secret(value: str) -> bool:
    text = value.strip()
    if len(text) < 6:
        return False
    if any(ch.isdigit() for ch in text) and any(ch.isalpha() for ch in text):
        return True
    return len(text) >= 12


def _scan_assignments(node: ast.AST, findings: list[SecretFinding], path: Path) -> None:
    for assignment in ast.walk(node):
        if isinstance(assignment, ast.Assign) and assignment.value and isinstance(assignment.value, ast.Constant) and isinstance(assignment.value.value, str):
            if not _looks_like_literal_secret(assignment.value.value):
                continue
            for target in assignment.targets:
                if isinstance(target, ast.Name) and _is_sensitive_name(target.id):
                    findings.append(
                        SecretFinding(
                            file=path,
                            line=getattr(assignment, "lineno", 1),
                            symbol=target.id,
                            value=assignment.value.value,
                        )
                    )


def _scan_keywords(node: ast.AST, findings: list[SecretFinding], path: Path) -> None:
    for call in ast.walk(node):
        if not isinstance(call, ast.Call) or not call.keywords:
            continue
        sensitive_pairs = [
            kw for kw in call.keywords
            if kw.arg
            and _is_sensitive_name(kw.arg)
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
            and _looks_like_literal_secret(kw.value.value)
        ]
        if len(sensitive_pairs) >= 1:
            for kw in sensitive_pairs:
                if not isinstance(kw.value, ast.Constant) or not isinstance(kw.value.value, str):
                    continue
                findings.append(
                    SecretFinding(
                        file=path,
                        line=getattr(call, "lineno", 1),
                        symbol=kw.arg or "<unknown>",
                        value=kw.value.value,
                    )
                )


def _scan_file(path: Path) -> list[SecretFinding]:
    text = path.read_text(encoding="utf-8")
    parsed = ast.parse(text, filename=str(path))
    findings: list[SecretFinding] = []
    _scan_assignments(parsed, findings, path)
    _scan_keywords(parsed, findings, path)
    return findings


def _resolve_paths(patterns: list[str]) -> list[Path]:
    result: list[Path] = []
    if not patterns:
        patterns = ["tests/test_*_parity.py", "tests/test_*_api.py", "tests/test_*_matrix.py"]
    for pattern in patterns:
        for path in Path(".").glob(pattern):
            if path.is_file() and path.suffix == ".py":
                result.append(path)
    return sorted(set(result))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        action="append",
        default=["tests/test_dual_mode_parity.py", "tests/test_backend_mutation_api.py"],
        help="Python file(s) or glob patterns to check.",
    )
    args = parser.parse_args()

    findings: list[SecretFinding] = []
    for pattern in args.path:
        target = Path(pattern)
        if target.exists() and target.is_file():
            findings.extend(_scan_file(target))
            continue

        for matched in _resolve_paths([pattern]):
            findings.extend(_scan_file(matched))

    if not findings:
        print("Secret hygiene check completed with no obvious hardcoded secrets in scanned targets.")
        return 0

    print("Potential hardcoded secrets found in scanned files:")
    for finding in findings:
        print(f"- {finding.file}:{finding.line}: {finding.symbol} = '{finding.value}'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
