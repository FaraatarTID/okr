from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_api_runtime_ignores_operator_state_and_exposes_read_only_inventory(
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "operator-state.json"
    state_file.write_text(
        json.dumps(
            {
                "environments": {
                    "env-recorded-by-cli": {
                        "environment_id": "env-recorded-by-cli",
                        "customer_id": "customer-a",
                        "deployment_profile": "single_tenant_saas",
                        "application_version": "release-1",
                        "state": "READY",
                    }
                },
                "audit_events": [],
            }
        ),
        encoding="utf-8",
    )
    probe = r"""
from fastapi.testclient import TestClient
import backend_app.main as main

main.app.dependency_overrides[main.require_service_access] = lambda: None
main.app.dependency_overrides[main.require_authenticated_principal] = lambda: {"username": "operator"}

client = TestClient(main.app)
inventory = client.get("/control-plane/environments")
detail = client.get("/control-plane/environments/env-recorded-by-cli")
retired_write = client.post(
    "/control-plane/environments/env-recorded-by-cli/lifecycle-events",
    json={"event": "SUSPEND"},
)
fleet = client.get("/control-plane/v1/rollouts/7")

assert inventory.status_code == 200, inventory.text
assert inventory.json() == {"environments": []}, inventory.text
assert detail.status_code == 404, detail.text
assert retired_write.status_code in {404, 405}, retired_write.text
assert fleet.status_code == 503, fleet.text

main.app.dependency_overrides[main.require_authenticated_principal] = lambda: {"username": "customer-user"}
customer_response = client.get("/control-plane/environments")
assert customer_response.status_code == 403, customer_response.text
"""
    environment = os.environ.copy()
    environment.update(
        {
            "OKR_ENV": "development",
            "OKR_BACKEND_ENFORCE_TOKEN": "false",
            "OKR_DATABASE_URL": "sqlite:///:memory:",
            "OKR_CONTROL_PLANE_STATE_PATH": str(state_file),
            "OKR_CONTROL_PLANE_OPERATORS": "operator",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
