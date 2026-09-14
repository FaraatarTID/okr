from __future__ import annotations

import pytest

from scripts.capture_compose_resources import aggregate_stats, parse_stats


def test_parse_stats_omits_container_id_and_sorts_containers() -> None:
    raw = '\n'.join([
        '{"Name":"okr-spa-bff-1","CPUPerc":"1.2%","MemUsage":"20MiB / 1GiB"}',
        '{"Name":"okr-backend-api-1","CPUPerc":"3.4%","MemUsage":"40MiB / 1GiB"}',
    ])

    assert parse_stats(raw) == [
        {"container": "okr-backend-api-1", "cpu_percent": "3.4%", "memory": "40MiB / 1GiB"},
        {"container": "okr-spa-bff-1", "cpu_percent": "1.2%", "memory": "20MiB / 1GiB"},
    ]


def test_parse_stats_rejects_malformed_input() -> None:
    with pytest.raises(ValueError, match="invalid docker stats JSON"):
        parse_stats("not-json")


def test_aggregate_stats_reports_peak_cpu_and_latest_memory() -> None:
    samples = [
        [{"container": "bff-1", "cpu_percent": "1.0%", "memory": "20MiB"}],
        [{"container": "bff-1", "cpu_percent": "3.5%", "memory": "22MiB"}],
    ]

    assert aggregate_stats(samples) == [
        {
            "container": "bff-1",
            "cpu_percent": "3.500%",
            "memory": "22MiB",
            "sample_count": 2,
        }
    ]


def test_aggregate_stats_rejects_inconsistent_container_sets() -> None:
    samples = [
        [{"container": "bff-1", "cpu_percent": "1.0%", "memory": "20MiB"}],
        [{"container": "api-1", "cpu_percent": "2.0%", "memory": "30MiB"}],
    ]

    with pytest.raises(ValueError, match="different container set"):
        aggregate_stats(samples)
