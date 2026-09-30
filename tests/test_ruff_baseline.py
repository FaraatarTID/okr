"""Ruff BLE and S findings may not grow past the recorded baseline.

`pyproject.toml` ignores the rules per file for files that already had findings when they were
enabled, and an ignore hides every finding of that rule in the file, old or new. This test runs
ruff with the per-file ignores switched off (`--isolated`) and compares the real counts with
`tests/ruff_baseline.json`, so a new blind `except Exception` or a new subprocess call in a
listed file fails here instead of disappearing. It fails on a decrease too: fix a finding, lower
its count in the baseline in the same change, so the number only moves one way.
"""

from __future__ import annotations

import collections
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "tests" / "ruff_baseline.json").read_text("utf-8"))[
    "files"
]


def _ruff(select: str, paths: list[str]) -> list[dict]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--select",
            select,
            "--output-format",
            "json",
            "--exit-zero",
            *paths,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _counts() -> dict[str, dict[str, int]]:
    found: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    findings = _ruff("BLE,S", ["alembic", "backend_app", "scripts", "src"])
    findings += _ruff("BLE", ["tests"])  # S is ignored in tests on purpose
    for item in findings:
        name = Path(item["filename"]).resolve().relative_to(ROOT).as_posix()
        found[name][item["code"]] += 1
    return {name: dict(sorted(c.items())) for name, c in sorted(found.items())}


@pytest.fixture(scope="module")
def current() -> dict[str, dict[str, int]]:
    return _counts()


def test_no_new_findings_beyond_the_baseline(current) -> None:
    grown = {
        f"{name}:{code}": (BASELINE.get(name, {}).get(code, 0), count)
        for name, codes in current.items()
        for code, count in codes.items()
        if count > BASELINE.get(name, {}).get(code, 0)
    }
    assert not grown, (
        "New ruff BLE/S findings (baseline, now): "
        f"{grown}. Fix them, or for an intentional one add a `# noqa: <code> - <reason>`. "
        "Do not raise the baseline."
    )


def test_fixed_findings_are_removed_from_the_baseline(current) -> None:
    stale = {
        f"{name}:{code}": (count, current.get(name, {}).get(code, 0))
        for name, codes in BASELINE.items()
        for code, count in codes.items()
        if current.get(name, {}).get(code, 0) < count
    }
    assert not stale, (
        f"Baseline entries above the real count (baseline, now): {stale}. "
        "Lower them in tests/ruff_baseline.json and pyproject.toml in the same change."
    )


def test_pyproject_ignores_exactly_the_files_in_the_baseline() -> None:
    """The two records of the baseline cannot drift apart."""
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    ignores = config["tool"]["ruff"]["lint"]["per-file-ignores"]
    per_file = {k: sorted(v) for k, v in ignores.items() if k != "tests/**"}
    expected = {name: sorted(codes) for name, codes in BASELINE.items()}
    assert per_file == expected


def test_the_scan_sees_the_repository(current) -> None:
    """A scan that found nothing would pass every test above."""
    assert len(current) >= 50
    assert sum(sum(c.values()) for c in current.values()) >= 100
    assert "src/services/ai_service.py" in current
