from pathlib import Path


def test_disposable_development_commands_are_isolated_and_documented() -> None:
    root = Path(__file__).resolve().parents[1]
    justfile = (root / "justfile").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    for command in ("dev-reset:", "dev-seed:", "dev-status:", "dev-clean:"):
        assert command in justfile
    assert "scripts/dev_workflow.py reset" in justfile
    assert "scripts/dev_workflow.py seed" in justfile
    assert "scripts/dev_workflow.py status" in justfile
    assert "scripts/dev_workflow.py clean" in justfile
    assert 'PROJECT = "okr-dev"' in (root / "scripts" / "dev_workflow.py").read_text(encoding="utf-8")
    assert "Docker Compose could not complete" in (root / "scripts" / "dev_workflow.py").read_text(encoding="utf-8")
    assert '"run", "--build", "--rm", "--no-deps", "backend-api"' in (
        root / "scripts" / "dev_workflow.py"
    ).read_text(encoding="utf-8")
    assert "COPY scripts/seed_dev_demo.py /app/scripts/seed_dev_demo.py" in (
        root / "deploy" / "docker" / "Dockerfile"
    ).read_text(encoding="utf-8")
    compose = (root / "deploy" / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count("OKR_DEV_DISPOSABLE=${OKR_DEV_DISPOSABLE:-}") == 2
    assert compose.count("OKR_ALLOW_NON_SUPABASE_DB=${OKR_ALLOW_NON_SUPABASE_DB:-false}") == 2
    assert "spa-web" in compose and "/api/healthz" in compose
    assert "--volumes --remove-orphans" not in justfile
    assert "just dev-reset" in readme
