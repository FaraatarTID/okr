from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
E2E_TEST_PATH = "tests/test_e2e_playwright_spa_login_to_atlas.py"


def _workflow() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_spa_e2e_waterfall_test_is_classified_and_scheduled() -> None:
    workflow = _workflow()
    changes = workflow["jobs"]["changes"]
    detect = next(step for step in changes["steps"] if step.get("id") == "filter")
    filters = yaml_load_filters(detect["with"]["filters"])
    frontend_patterns = [pattern for pattern in filters["frontend"] if not pattern.startswith("!")]

    assert any(fnmatchcase(E2E_TEST_PATH, pattern) for pattern in frontend_patterns), (
        "the browser waterfall test is test-only, so its path must match the frontend "
        "classifier and schedule the spa-e2e job"
    )

    spa_e2e = workflow["jobs"]["spa-e2e"]
    assert {"changes", "spa-quality"}.issubset(set(spa_e2e["needs"]))
    condition = spa_e2e["if"]
    for category in ("frontend", "shared", "unclassified"):
        assert f"needs.changes.outputs.{category} == 'true'" in condition


def yaml_load_filters(raw: str) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.load(raw, Loader=yaml.BaseLoader)
