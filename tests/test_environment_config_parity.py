from pathlib import Path

from scripts.check_environment_config_parity import check_parity


def test_matching_config_shape_passes(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.env"
    staging = tmp_path / "staging.env"
    canonical.write_text(
        "FLAG=true\nCOUNT=1\nSERVICE_URL=http://api\n", encoding="utf-8"
    )
    staging.write_text(
        "FLAG=false\nCOUNT=2\nSERVICE_URL=http://other\nEXTRA=value\n", encoding="utf-8"
    )

    assert check_parity(canonical, staging) == []


def test_config_shape_failure_does_not_expose_secret_values(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.env"
    staging = tmp_path / "staging.env"
    canonical.write_text("SERVICE_TOKEN=canonical-private-value\n", encoding="utf-8")
    staging.write_text("", encoding="utf-8")

    failures = check_parity(canonical, staging)

    assert "canonical-private-value" not in "\n".join(failures)
    assert failures == ["staging template is missing configuration key SERVICE_TOKEN"]
