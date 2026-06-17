from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = ROOT / "docs" / "HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.json"
ATLAS_SHELL_PATH = ROOT / "spa-web" / "src" / "components" / "AtlasShell.tsx"
ATLAS_SHELL_COMPONENTS_DIR = ROOT / "spa-web" / "src" / "components" / "atlas-shell"
ROLLOUT_LIB_PATH = ROOT / "spa-web" / "src" / "lib" / "rollout.ts"
ROLLOUT_ROUTE_PATH = ROOT / "spa-web" / "src" / "app" / "api" / "rollout" / "route.ts"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict)
    return payload


def _load_spa_shell_source_bundle() -> str:
    parts = [ATLAS_SHELL_PATH.read_text(encoding="utf-8")]
    if ATLAS_SHELL_COMPONENTS_DIR.exists():
        for path in sorted(ATLAS_SHELL_COMPONENTS_DIR.glob("*.tsx")):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_spa_shell_validation_record_shape() -> None:
    payload = _load_json(VALIDATION_PATH)

    for key in (
        "id",
        "date",
        "work_item",
        "source_files",
        "required_navigation_controls",
        "required_sections",
        "role_aware_entrypoints",
        "result",
    ):
        assert key in payload

    assert payload["work_item"] == "HFM-030"
    parsed_date = date.fromisoformat(str(payload["date"]))
    assert parsed_date == date(2026, 2, 25)

    controls = payload["required_navigation_controls"]
    assert isinstance(controls, list) and controls
    sections = payload["required_sections"]
    assert isinstance(sections, list) and sections


def test_spa_shell_validation_controls_and_sections_exist_in_component() -> None:
    payload = _load_json(VALIDATION_PATH)
    atlas_shell_source = ATLAS_SHELL_PATH.read_text(encoding="utf-8")
    source_bundle = _load_spa_shell_source_bundle()

    for control in payload["required_navigation_controls"]:
        control_id = str(control["control_id"])
        assert control.get("present") is True
        assert f'id="{control_id}"' in source_bundle

    for section in payload["required_sections"]:
        label = str(section["label"])
        assert section.get("present") is True
        assert label in source_bundle


def test_spa_shell_validation_role_aware_entrypoints_match_rollout_logic() -> None:
    payload = _load_json(VALIDATION_PATH)
    entrypoints = payload["role_aware_entrypoints"]
    assert isinstance(entrypoints, dict)

    rollout_lib = ROLLOUT_LIB_PATH.read_text(encoding="utf-8")
    rollout_route = ROLLOUT_ROUTE_PATH.read_text(encoding="utf-8")
    atlas_shell = ATLAS_SHELL_PATH.read_text(encoding="utf-8")

    for env_key in entrypoints["rollout_config_env_keys"]:
        assert str(env_key) in rollout_route

    for decision in entrypoints["decision_paths"]:
        assert f'"{decision}"' in rollout_lib

    assert entrypoints.get("ui_rollout_status_message_present") is True
    assert "rolloutMessage" in atlas_shell

    result = payload["result"]
    assert isinstance(result, dict)
    assert result.get("acceptance_met") is True
