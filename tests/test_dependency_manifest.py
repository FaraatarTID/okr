"""Behavioural tests for the dependency-manifest and release-digest gates.

The previous version of this file asserted that particular strings appeared in the
scripts' own source - `"64"`, `"_locked_versions"`, `"declared="`. Those assertions
cannot distinguish a working check from a broken one: they keep passing if the
comparison is inverted, short-circuited, or deleted outright, so long as the
identifier survives somewhere in the file. They certified the presence of a symbol,
not the operation of a control.

These tests call the real functions with deliberately broken input instead, and pair
every rejection with an acceptance so neither direction can pass vacuously.

`check_dependency_manifest` resolves its inputs from module-level constants, so the
fixture repoints those at a temporary tree rather than mutating the repository.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GOOD_PYPROJECT = """
[project]
name = "example"
dependencies = ["foo==1.0.0"]

[dependency-groups]
dev = []
"""

_GOOD_LOCK = """
[[package]]
name = "foo"
version = "1.0.0"
"""


@pytest.fixture()
def manifest(tmp_path, monkeypatch):
    module = _load("check_dependency_manifest")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    requirements_path = tmp_path / "backend_app" / "requirements.txt"
    monkeypatch.setattr(module, "REQUIREMENTS_PATH", requirements_path)

    def write(
        *, requirements: str, pyproject: str = _GOOD_PYPROJECT, lock: str = _GOOD_LOCK
    ):
        (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        (tmp_path / "uv.lock").write_text(lock, encoding="utf-8")
        requirements_path.parent.mkdir(parents=True, exist_ok=True)
        requirements_path.write_text(requirements, encoding="utf-8")

    return module, write


def test_a_consistent_manifest_reports_no_drift(manifest):
    # The acceptance half. Without it, every rejection test below would pass just as
    # well against a check() that always reports a failure.
    module, write = manifest
    write(requirements="foo==1.0.0\n")

    assert module.check() == []


def test_a_compatibility_export_that_drifts_is_reported(manifest):
    module, write = manifest
    write(requirements="foo==2.0.0\n")

    failures = module.check()

    assert failures, (
        "drift between the authority and the compatibility export was not reported"
    )
    assert any("foo" in failure for failure in failures), failures


def test_a_version_disagreeing_with_the_lock_is_reported(manifest):
    # requirements agree with the authority, so only the uv.lock comparison can catch
    # this - the second half of check(), which the old string assertion never reached.
    module, write = manifest
    write(
        requirements="foo==1.0.0\n",
        lock="""
[[package]]
name = "foo"
version = "9.9.9"
""",
    )

    failures = module.check()

    assert failures, "a lock-file version disagreement was not reported"
    assert any("locked" in failure for failure in failures), failures


def test_an_unpinned_declaration_is_rejected_rather_than_ignored(manifest):
    module, write = manifest
    write(requirements="foo\n")

    failures = module.check()

    assert failures, "an unpinned requirements entry was accepted silently"


def test_a_missing_compatibility_export_is_reported(manifest):
    module, write = manifest
    write(requirements="")

    failures = module.check()

    assert failures, "a missing compatibility export was treated as agreement"


_GROUPED_PYPROJECT = """
[project]
name = "example"
dependencies = ["foo==1.0.0"]

[dependency-groups]
browser = ["bar==2.0.0"]
dev = [{include-group = "browser"}, "baz==3.0.0"]
"""

_GROUPED_LOCK = """
[[package]]
name = "foo"
version = "1.0.0"

[[package]]
name = "bar"
version = "2.0.0"

[[package]]
name = "baz"
version = "3.0.0"
"""


def test_a_group_included_by_dev_is_part_of_the_authority(manifest):
    module, write = manifest
    write(
        requirements="bar==2.0.0\nbaz==3.0.0\nfoo==1.0.0\n",
        pyproject=_GROUPED_PYPROJECT,
        lock=_GROUPED_LOCK,
    )

    assert module.check() == []


def test_an_export_missing_an_included_group_member_is_reported(manifest):
    # Pairs with the test above: the include is followed, so dropping its member drifts.
    module, write = manifest
    write(
        requirements="baz==3.0.0\nfoo==1.0.0\n",
        pyproject=_GROUPED_PYPROJECT,
        lock=_GROUPED_LOCK,
    )

    failures = module.check()

    assert any("bar" in failure for failure in failures), failures


def test_a_group_include_cycle_is_reported_not_recursed_forever(manifest):
    module, write = manifest
    write(
        requirements="foo==1.0.0\n",
        pyproject="""
[project]
name = "example"
dependencies = ["foo==1.0.0"]

[dependency-groups]
dev = [{include-group = "other"}]
other = [{include-group = "dev"}]
""",
    )

    failures = module.check()

    assert any("cycle" in failure for failure in failures), failures


def test_an_unsupported_group_entry_is_reported(manifest):
    module, write = manifest
    write(
        requirements="foo==1.0.0\n",
        pyproject="""
[project]
name = "example"
dependencies = ["foo==1.0.0"]

[dependency-groups]
dev = [{something-else = "x"}]
""",
    )

    failures = module.check()

    assert any("Unsupported dependency group entry" in failure for failure in failures)


def test_playwright_is_a_dev_and_browser_group_member_not_a_runtime_dependency():
    """The backend image installs `--no-dev`; CI installs `--group dev` and needs Playwright."""
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = [str(item).lower() for item in data["project"]["dependencies"]]
    groups = data["dependency-groups"]

    assert not any(item.startswith("playwright") for item in runtime)
    assert any(str(i).startswith("playwright==") for i in groups["browser"])
    assert {"include-group": "browser"} in groups["dev"]


def test_the_backend_image_installs_the_browser_group_only_on_request():
    dockerfile = (ROOT / "deploy" / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG INSTALL_BROWSER_GROUP=false" in dockerfile
    assert "--no-dev" in dockerfile
    assert '"$INSTALL_BROWSER_GROUP" = "true"' in dockerfile
    assert "--group browser" in dockerfile


def test_release_renderer_rejects_a_digest_that_is_not_64_hex():
    module = _load("render_k8s_release")

    with pytest.raises(ValueError):
        module._validate_digest("sha256:abc123", "api_digest")


def test_release_renderer_rejects_the_unresolved_placeholder():
    module = _load("render_k8s_release")

    with pytest.raises(ValueError):
        module._validate_digest("REPLACE_WITH_RELEASE_DIGEST", "api_digest")


def test_release_renderer_accepts_a_valid_sha256_digest():
    # The acceptance half for the digest gate, so the rejections above cannot be
    # satisfied by a validator that refuses everything.
    module = _load("render_k8s_release")

    digest = "a" * 64

    assert module._validate_digest(f"sha256:{digest}", "api_digest") == digest
