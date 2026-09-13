from __future__ import annotations

import socket

from scripts.verify_postgresql_integration import _available_port


def test_postgresql_verifier_moves_to_an_available_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        preferred = int(occupied.getsockname()[1])

        selected = _available_port(preferred)

    assert selected != preferred
    assert selected > 0
