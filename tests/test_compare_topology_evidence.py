from __future__ import annotations

import pytest

from scripts.compare_topology_evidence import EvidenceError, compare, compare_resources


def _evidence(url: str, measured: float, passed: bool = True) -> dict:
    return {
        "schema_version": 1,
        "release_id": "release-a",
        "captured_at": "2026-01-01T00:00:00Z",
        "operator": "operator",
        "topology": "bff",
        "base_url": url,
        "results": [
            {"slo": "healthz", "measured_s": measured, "pass": passed},
        ],
    }


def test_compare_reports_delta_and_keeps_human_decision() -> None:
    report = compare(_evidence("http://bff", 2.0), _evidence("http://direct", 1.5))

    assert report["decision"] == "human_review_required"
    assert report["candidate_passed"] == 1
    assert report["comparisons"][0]["delta_s"] == -0.5
    assert report["comparisons"][0]["relative_change_pct"] == -25.0


def test_compare_requires_matching_slo_sets() -> None:
    candidate = {
        **_evidence("http://direct", 1.0),
        "results": [{"slo": "different", "measured_s": 1.0, "pass": True}],
    }
    with pytest.raises(EvidenceError, match="same SLOs"):
        compare(_evidence("http://bff", 1.0), candidate)


def test_compare_rejects_different_release_ids() -> None:
    candidate = _evidence("http://direct", 1.0)
    candidate["release_id"] = "release-b"

    with pytest.raises(EvidenceError, match="same release_id"):
        compare(_evidence("http://bff", 1.0), candidate)


def test_compare_resources_reports_cpu_delta() -> None:
    baseline = {
        "services": [{"container": "bff-1", "cpu_percent": "2.0%", "memory": "20MiB"}]
    }
    candidate = {
        "services": [{"container": "bff-1", "cpu_percent": "3.5%", "memory": "22MiB"}]
    }

    assert compare_resources(baseline, candidate) == [
        {
            "container": "bff-1",
            "baseline_cpu_percent": 2.0,
            "candidate_cpu_percent": 3.5,
            "cpu_delta_percent": 1.5,
            "baseline_memory": "20MiB",
            "candidate_memory": "22MiB",
            "baseline_sample_count": 1,
            "candidate_sample_count": 1,
        }
    ]


def test_compare_resources_supports_logical_mapping_for_different_topologies() -> None:
    baseline = {
        "services": [
            {"container": "bff-api-1", "cpu_percent": "2.0%", "memory": "20MiB"}
        ]
    }
    candidate = {
        "services": [
            {"container": "direct-api-1", "cpu_percent": "1.0%", "memory": "18MiB"}
        ]
    }

    result = compare_resources(
        baseline,
        candidate,
        resource_map={"api": {"baseline": "bff-api-1", "candidate": "direct-api-1"}},
    )

    assert result[0]["container"] == "api"
    assert result[0]["cpu_delta_percent"] == -1.0


def test_compare_resources_rejects_unknown_mapping_container() -> None:
    with pytest.raises(EvidenceError, match="unknown container"):
        compare_resources(
            {"services": [{"container": "bff-api-1", "cpu_percent": "2.0%"}]},
            {"services": [{"container": "direct-api-1", "cpu_percent": "1.0%"}]},
            resource_map={"api": {"baseline": "missing", "candidate": "direct-api-1"}},
        )
