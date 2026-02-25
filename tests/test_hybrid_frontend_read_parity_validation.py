from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = ROOT / "docs" / "HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.json"
FIXTURE_PATH = ROOT / "docs" / "fixtures" / "hybrid_frontend" / "atlas_snapshot.response.json"
ATLAS_LIB_PATH = ROOT / "spa-web" / "src" / "lib" / "atlas.ts"
ATLAS_SHELL_PATH = ROOT / "spa-web" / "src" / "components" / "AtlasShell.tsx"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict)
    return payload


def _count_tree(snapshot: dict[str, Any]) -> dict[str, int]:
    goals = snapshot.get("goals") or []
    objective_count = 0
    key_result_count = 0
    task_count = 0

    for goal in goals:
        objectives = goal.get("objectives") or []
        objective_count += len(objectives)
        for objective in objectives:
            key_results = objective.get("key_results") or []
            key_result_count += len(key_results)
            for key_result in key_results:
                task_count += len(key_result.get("tasks") or [])

    return {
        "goals": len(goals),
        "objectives": objective_count,
        "key_results": key_result_count,
        "tasks": task_count,
    }


def test_read_parity_validation_record_shape() -> None:
    payload = _load_json(VALIDATION_PATH)

    for key in (
        "id",
        "date",
        "work_item",
        "fixture_source",
        "spa_sources",
        "pilot_fixture_counts",
        "required_read_fields",
        "focus_map_inspector_render_signals",
        "result",
    ):
        assert key in payload

    assert payload["work_item"] == "HFM-031"
    parsed_date = date.fromisoformat(str(payload["date"]))
    assert parsed_date == date(2026, 2, 25)


def test_read_parity_validation_fixture_counts_match_record() -> None:
    payload = _load_json(VALIDATION_PATH)
    snapshot = _load_json(FIXTURE_PATH)

    counted = _count_tree(snapshot)
    expected = payload["pilot_fixture_counts"]
    assert counted == {
        "goals": int(expected["goals"]),
        "objectives": int(expected["objectives"]),
        "key_results": int(expected["key_results"]),
        "tasks": int(expected["tasks"]),
    }


def test_read_parity_validation_required_fields_exist_in_fixture() -> None:
    payload = _load_json(VALIDATION_PATH)
    snapshot = _load_json(FIXTURE_PATH)
    required = payload["required_read_fields"]

    goals = snapshot["goals"]
    assert goals
    goal = goals[0]
    for field in required["goal"]:
        assert field in goal

    objective = goal["objectives"][0]
    for field in required["objective"]:
        assert field in objective

    key_result = objective["key_results"][0]
    for field in required["key_result"]:
        assert field in key_result

    task = key_result["tasks"][0]
    for field in required["task"]:
        assert field in task


def test_read_parity_validation_spa_sources_expose_read_parity_signals() -> None:
    payload = _load_json(VALIDATION_PATH)
    atlas_lib = ATLAS_LIB_PATH.read_text(encoding="utf-8")
    atlas_shell = ATLAS_SHELL_PATH.read_text(encoding="utf-8")

    for marker in (
        "export interface AtlasGoalSnapshot",
        "export interface AtlasObjectiveSnapshot",
        "export interface AtlasKeyResultSnapshot",
        "export interface AtlasTaskSnapshot",
        "users_map",
    ):
        assert marker in atlas_lib

    render_signals = payload["focus_map_inspector_render_signals"]
    assert render_signals.get("focus_map_section_present") is True
    assert render_signals.get("inspector_section_present") is True

    for label in ("Focus Map", "Inspector"):
        assert label in atlas_shell

    for inspector_field in render_signals["inspector_fields_present"]:
        assert str(inspector_field) in atlas_shell

    result = payload["result"]
    assert isinstance(result, dict)
    assert result.get("acceptance_met") is True
