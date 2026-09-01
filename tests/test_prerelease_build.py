from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "deploy" / "darkube" / "prerelease" / "README.md"


def _dockerfile(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _context_copy_sources(dockerfile: str) -> list[str]:
    sources: list[str] = []
    for line in dockerfile.splitlines():
        stripped = line.strip()
        if not stripped.startswith("COPY ") or "--from=" in stripped:
            continue
        match = re.match(r"COPY\s+(.+)$", stripped)
        assert match is not None
        parts = match.group(1).split()
        sources.extend(parts[:-1])
    return sources


def _assert_context_inputs(context: Path, dockerfile_path: str) -> None:
    dockerfile = _dockerfile(dockerfile_path)
    assert (ROOT / dockerfile_path).is_file()
    for source in _context_copy_sources(dockerfile):
        if "*" in source:
            assert list(context.glob(source)), f"missing build input: {source}"
        else:
            assert (context / source).exists(), f"missing build input: {source}"


def test_backend_api_and_worker_use_root_context_and_shared_dockerfile() -> None:
    _assert_context_inputs(ROOT, "deploy/docker/Dockerfile")
    dockerfile = _dockerfile("deploy/docker/Dockerfile")
    assert 'CMD ["python", "-m", "backend_app.run_api"]' in dockerfile
    assert (ROOT / "backend_app").is_dir()

    readme = README_PATH.read_text(encoding="utf-8")
    assert "| API | `okr-prerelease-api` | `ghcr.io/<owner>/<repository>/backend:<commit-sha>`" in readme
    assert "| Worker | `okr-prerelease-worker` | `ghcr.io/<owner>/<repository>/backend:<commit-sha>`" in readme
    assert "`python -m backend_app.worker`" in readme


def test_bff_uses_spa_bff_context_and_dockerfile() -> None:
    _assert_context_inputs(ROOT / "spa-bff", "spa-bff/Dockerfile")
    dockerfile = _dockerfile("spa-bff/Dockerfile")
    assert 'CMD ["node", "dist/src/server.js"]' in dockerfile
    assert "COPY --from=build /app/dist ./dist" in dockerfile

    readme = README_PATH.read_text(encoding="utf-8")
    assert "| BFF | `okr-prerelease-bff` | `ghcr.io/<owner>/<repository>/bff:<commit-sha>`" in readme


def test_web_uses_spa_web_context_and_dockerfile() -> None:
    _assert_context_inputs(ROOT / "spa-web", "spa-web/Dockerfile")
    dockerfile = _dockerfile("spa-web/Dockerfile")
    assert 'ENV PORT=3000' in dockerfile
    assert 'CMD ["npm", "run", "start"]' in dockerfile
    assert "COPY --from=build /app/.next ./.next" in dockerfile

    readme = README_PATH.read_text(encoding="utf-8")
    assert "| Web | `okr-prerelease-web` | `ghcr.io/<owner>/<repository>/web:<commit-sha>`" in readme


def test_backend_commands_are_distinct_and_explicit() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    api_row = next(line for line in readme.splitlines() if line.startswith("| API |"))
    worker_row = next(line for line in readme.splitlines() if line.startswith("| Worker |"))
    assert "`python -m backend_app.run_api`" in api_row
    assert "`python -m backend_app.worker`" in worker_row
    assert api_row != worker_row
