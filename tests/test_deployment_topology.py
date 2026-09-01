from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_deployment_topology import TopologyError, validate_compose_text


COMPOSE = Path(__file__).resolve().parents[1] / "deploy" / "docker" / "docker-compose.yml"


def test_committed_compose_has_the_required_private_topology() -> None:
    validate_compose_text(COMPOSE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("- \"0.0.0.0:8100:8100\"", "backend-api published port binds to public host"),
        ("- \"0.0.0.0:15432:5432\"", "postgres published port binds to public host"),
        ("OKR_BACKEND_API_URL=http://public.example:8100", "must target the private backend service"),
    ],
)
def test_rejects_public_backend_or_database_ingress(replacement: str, message: str) -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    if replacement.startswith("OKR_"):
        text = text.replace(
            "OKR_BACKEND_API_URL=${OKR_BACKEND_API_URL:-http://backend-api:8100}",
            replacement,
        )
    elif "8100" in replacement:
        text = text.replace(
            '"${OKR_BACKEND_BIND_ADDRESS:-127.0.0.1}:${OKR_BACKEND_HOST_PORT:-8100}:${OKR_BACKEND_PORT:-8100}"',
            replacement,
        )
    else:
        text = text.replace(
            '"${OKR_POSTGRES_BIND_ADDRESS:-127.0.0.1}:${OKR_POSTGRES_HOST_PORT:-15432}:5432"',
            replacement,
        )
    with pytest.raises(TopologyError, match=message):
        validate_compose_text(text)
