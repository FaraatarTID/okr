from __future__ import annotations

from pathlib import Path

from src.ui import session_keys


def test_validate_atlas_key_lifecycle_policy_has_no_errors():
    assert session_keys.validate_atlas_key_lifecycle_policy() == []


def test_navigation_bundles_reference_governed_keys():
    governed_keys = set(session_keys.ATLAS_FIXED_SESSION_KEYS)
    assert set(session_keys.CYCLE_CHANGE_KEYS).issubset(governed_keys)
    assert set(session_keys.HOME_NAV_KEYS).issubset(set(session_keys.CYCLE_CHANGE_KEYS))


def test_atlas_fixed_keys_are_not_used_as_raw_string_literals():
    ui_dir = Path(__file__).resolve().parents[1] / "streamlit_app" / "src" / "ui"
    offenders: list[str] = []

    for path in sorted(ui_dir.rglob("*.py")):
        if path.name == "session_keys.py":
            continue
        text = path.read_text(encoding="utf-8")
        for key in session_keys.ATLAS_FIXED_SESSION_KEYS:
            if f'"{key}"' in text or f"'{key}'" in text:
                offenders.append(f"{path.relative_to(ui_dir)} -> {key}")

    assert not offenders, (
        "Raw atlas session keys found outside session_keys.py:\n" + "\n".join(offenders)
    )
