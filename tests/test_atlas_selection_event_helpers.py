from types import SimpleNamespace

from src.ui import atlas_selection_event_helpers


def test_atlas_extract_clicked_ref_supports_customdata_and_index_fallback():
    point_with_custom = {"customdata": ["task_7"]}
    assert (
        atlas_selection_event_helpers.atlas_extract_clicked_ref(point_with_custom)
        == "task_7"
    )

    point_with_idx = {"pointIndex": 1}
    point_refs = ["task_1", "task_2"]
    assert (
        atlas_selection_event_helpers.atlas_extract_clicked_ref(
            point_with_idx,
            point_refs=point_refs,
        )
        == "task_2"
    )


def test_atlas_extract_clicked_ref_from_points_prefers_deepest_ref_in_index():
    points = [{"customdata": ["objective_1"]}, {"customdata": ["task_9"]}]
    index = {
        "objective_1": {"depth": 1},
        "task_9": {"depth": 3},
    }
    assert (
        atlas_selection_event_helpers.atlas_extract_clicked_ref_from_points(
            points,
            index=index,
        )
        == "task_9"
    )


def test_atlas_extract_selection_points_handles_list_and_object_payloads():
    assert atlas_selection_event_helpers.atlas_extract_selection_points([{"a": 1}]) == [
        {"a": 1}
    ]

    payload_obj = SimpleNamespace(selection=SimpleNamespace(points=[{"id": "x"}]))
    assert atlas_selection_event_helpers.atlas_extract_selection_points(
        payload_obj
    ) == [{"id": "x"}]
