from __future__ import annotations

import os
import subprocess
import sys


def test_main_import_route_guard_is_enforced():
    script = (
        "import sys\n"
        "import backend_app.main_bootstrap_helpers as helpers\n"
        "\n"
        "helpers._REQUIRED_MUTATION_ROUTES = {('POST', '/v1/does/not/exist')}\n"
        "sys.modules.pop('backend_app.main', None)\n"
        "\n"
        "try:\n"
        "    import backend_app.main\n"
        "except RuntimeError as exc:\n"
        "    print(f'ROUTE_BOOTSTRAP_ASSERTED:{exc}')\n"
        "else:\n"
        "    print('ROUTE_IMPORT_SUCCEEDED')\n"
        "    raise SystemExit(1)\n"
    )

    process = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )

    assert process.returncode == 0
    assert "ROUTE_BOOTSTRAP_ASSERTED:Required route missing during bootstrap" in process.stdout
