from __future__ import annotations

import ast
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
E2E_TEST_PATH = "tests/test_e2e_playwright_spa_login_to_atlas.py"


def _workflow() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_spa_e2e_waterfall_test_is_classified_and_scheduled() -> None:
    workflow = _workflow()
    changes = workflow["jobs"]["changes"]
    detect = next(step for step in changes["steps"] if step.get("id") == "filter")
    filters = yaml_load_filters(detect["with"]["filters"])
    frontend_patterns = [
        pattern for pattern in filters["frontend"] if not pattern.startswith("!")
    ]

    assert any(fnmatchcase(E2E_TEST_PATH, pattern) for pattern in frontend_patterns), (
        "the browser waterfall test is test-only, so its path must match the frontend "
        "classifier and schedule the spa-e2e job"
    )

    spa_e2e = workflow["jobs"]["spa-e2e"]
    assert {"changes", "spa-quality"}.issubset(set(spa_e2e["needs"]))
    condition = spa_e2e["if"]
    for category in ("frontend", "shared", "unclassified"):
        assert f"needs.changes.outputs.{category} == 'true'" in condition


def test_e2e_stack_cleanup_uses_only_owned_process_handles() -> None:
    source = (ROOT / E2E_TEST_PATH).read_text(encoding="utf-8")
    module = ast.parse(source)
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_terminate_port_listener" not in functions, (
        "port-wide process discovery can terminate a process not started by the fixture"
    )
    terminate_process = functions["_terminate_process"]
    taskkill_calls = [
        node
        for node in ast.walk(terminate_process)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
        and node.args
        and isinstance(node.args[0], ast.List)
        and node.args[0].elts
        and isinstance(node.args[0].elts[0], ast.Constant)
        and node.args[0].elts[0].value == "taskkill"
    ]
    assert len(taskkill_calls) == 1
    taskkill_args = taskkill_calls[0].args[0]
    assert isinstance(taskkill_args, ast.List)
    owned_pid_argument = taskkill_args.elts[2]
    assert (
        isinstance(owned_pid_argument, ast.Call)
        and isinstance(owned_pid_argument.func, ast.Name)
        and owned_pid_argument.func.id == "str"
        and len(owned_pid_argument.args) == 1
        and isinstance(owned_pid_argument.args[0], ast.Attribute)
        and isinstance(owned_pid_argument.args[0].value, ast.Name)
        and owned_pid_argument.args[0].value.id == "process"
        and owned_pid_argument.args[0].attr == "pid"
    ), "Windows cleanup must target the process handle owned by the fixture"

    stack_fixture = functions["e2e_stack"]
    owned_processes = {
        "spa_process",
        "bff_process",
        "backend_process",
        "worker_process",
    }
    cleanup_calls = {
        node.args[0].id
        for node in ast.walk(stack_fixture)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_terminate_process"
        and node.args
        and isinstance(node.args[0], ast.Name)
    }
    assert owned_processes.issubset(cleanup_calls)
    fixture_calls = {
        node.func.id
        for node in ast.walk(stack_fixture)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {
        "_capture_next_typegen_files",
        "_restore_next_typegen_files",
    }.issubset(fixture_calls)


def test_e2e_next_dist_dir_override_is_project_local_and_optional() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to evaluate the installed Next.js config.")
    assert node is not None

    spa_root = ROOT / "spa-web"
    script = (
        "import config from './next.config.ts'; console.log(JSON.stringify(config));"
    )
    base_env = os.environ.copy()
    base_env.pop("OKR_E2E_NEXT_DIST_DIR", None)

    default_result = subprocess.run(
        [
            node,
            "--no-warnings",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            script,
        ],
        cwd=spa_root,
        env=base_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert default_result.returncode == 0, default_result.stderr
    default_config = json.loads(default_result.stdout)
    assert "distDir" not in default_config
    assert "reactStrictMode" not in default_config

    isolated_env = base_env.copy()
    isolated_env["OKR_E2E_NEXT_DIST_DIR"] = ".next/e2e-45678"
    isolated_result = subprocess.run(
        [
            node,
            "--no-warnings",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            script,
        ],
        cwd=spa_root,
        env=isolated_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert isolated_result.returncode == 0, isolated_result.stderr
    isolated_config = json.loads(isolated_result.stdout)
    assert Path(isolated_config["distDir"]) == Path(".next") / "e2e-45678"
    assert isolated_config["reactStrictMode"] is False

    escaping_env = base_env.copy()
    escaping_env["OKR_E2E_NEXT_DIST_DIR"] = "../outside-spa"
    escaping_result = subprocess.run(
        [
            node,
            "--no-warnings",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            script,
        ],
        cwd=spa_root,
        env=escaping_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert escaping_result.returncode != 0


def yaml_load_filters(raw: str) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.load(raw, Loader=yaml.BaseLoader)
