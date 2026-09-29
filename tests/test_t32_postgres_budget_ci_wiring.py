from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def test_backend_quality_requires_real_postgres_for_budget_tests() -> None:
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    backend_quality = workflow["jobs"]["backend-quality"]

    assert "postgres" in backend_quality["services"]
    assert backend_quality["env"]["OKR_TEST_POSTGRES_URL"].startswith(
        "postgresql+psycopg://"
    )
    assert backend_quality["env"]["OKR_REQUIRE_TEST_POSTGRES_URL"].lower() == "true"
