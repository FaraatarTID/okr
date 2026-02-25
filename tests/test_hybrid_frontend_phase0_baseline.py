from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "docs" / "HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict)
    return payload


def test_phase0_baseline_record_shape() -> None:
    payload = _load_json(BASELINE_PATH)
    for key in ("id", "date", "work_item", "commands", "result"):
        assert key in payload

    assert payload["work_item"] == "HFM-000"
    assert date.fromisoformat(str(payload["date"])) == date(2026, 2, 25)

    commands = payload["commands"]
    assert isinstance(commands, list) and len(commands) == 3
    for command in commands:
        assert isinstance(command, dict)
        for key in ("name", "command", "exit_code", "status", "summary", "notes"):
            assert key in command


def test_phase0_baseline_required_command_outcomes() -> None:
    payload = _load_json(BASELINE_PATH)
    by_name = {str(item["name"]): item for item in payload["commands"]}

    assert {"pytest_baseline", "playwright_happy_path", "runtime_config_gate"} == set(
        by_name.keys()
    )

    pytest_cmd = by_name["pytest_baseline"]
    assert pytest_cmd["command"] == "python -m pytest -q"
    assert int(pytest_cmd["exit_code"]) == 0
    assert pytest_cmd["status"] == "pass"

    playwright_cmd = by_name["playwright_happy_path"]
    assert "tests/test_e2e_playwright_login_to_atlas.py" in str(playwright_cmd["command"])
    assert int(playwright_cmd["exit_code"]) == 0
    assert str(playwright_cmd["status"]) in {"pass", "skipped"}
    if playwright_cmd["status"] == "skipped":
        assert "Playwright" in str(playwright_cmd["notes"])

    runtime_cmd = by_name["runtime_config_gate"]
    assert "scripts/check_deploy_config.py --mode runtime" in str(runtime_cmd["command"])
    assert int(runtime_cmd["exit_code"]) == 0
    assert runtime_cmd["status"] == "pass"

    result = payload["result"]
    assert isinstance(result, dict)
    assert result.get("acceptance_met") is True
