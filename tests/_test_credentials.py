from __future__ import annotations

import hashlib
import os


def credential_password(name: str, *, length: int = 16) -> str:
    """Return a deterministic, environment-driven test password for stable payloads.

    The value is intentionally deterministic by default so tests remain reproducible
    while allowing CI/local overrides through env vars when stronger/longer secrets
    are needed for specific runs.
    """

    if length <= 0:
        return ""

    seed = os.environ.get(
        f"OKR_TEST_{name.upper()}_PASSWORD_SEED",
        os.environ.get("OKR_TEST_PASSWORD_SEED", "okr_test_password_seed"),
    )
    digest = hashlib.sha256(f"{seed}:{name}".encode("utf-8")).hexdigest()
    return digest[:length]
