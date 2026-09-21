"""Tests for the workflow secret prerequisite gate.

The gate exists because `publish-ghcr.yml` required
`OKR_RELEASE_MANIFEST_ATTESTATION_SECRET` while no such repository secret existed,
and because that workflow triggers only on push, no pull request could observe the
failure. These tests cover the checker's own logic and assert that the repository
declaration is currently consistent with the workflows.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_workflow_secret_prerequisites import (
    DECLARATION,
    ROOT,
    WORKFLOWS_DIR,
    load_declaration,
    main,
    problems,
    referenced_secrets,
    scan,
    triggers_on_pull_request,
)


def test_automatic_secrets_are_not_prerequisites():
    text = "token: ${{ secrets.GITHUB_TOKEN }}\nkey: ${{ secrets.MY_KEY }}\n"
    assert referenced_secrets(text) == {"MY_KEY"}


def test_a_commented_out_reference_is_not_a_prerequisite():
    text = "on:\n  pull_request:\n# key: ${{ secrets.DISABLED_KEY }}\n"
    assert referenced_secrets(text) == set()


def test_pull_request_trigger_is_detected_in_block_form():
    text = "on:\n  pull_request:\n  push:\n    branches: [main]\n"
    assert triggers_on_pull_request(text) is True


def test_pull_request_trigger_is_detected_in_inline_form():
    assert triggers_on_pull_request("on: [push, pull_request]\n") is True


def test_push_only_trigger_is_not_pr_checkable():
    text = "on:\n  push:\n    branches: [main]\n"
    assert triggers_on_pull_request(text) is False


def test_pull_request_in_a_later_job_body_does_not_count():
    """A `pull_request` outside the `on:` block must not be mistaken for a trigger."""
    text = (
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  build:\n"
        "    if: github.event_name == 'pull_request'\n"
    )
    assert triggers_on_pull_request(text) is False


def test_an_undeclared_secret_is_reported():
    derived = {"NEW_SECRET": {"workflows": ["x.yml"], "all_post_merge_only": False}}
    findings = problems(derived, {})
    assert len(findings) == 1
    assert "NEW_SECRET" in findings[0]
    assert "not declared" in findings[0]


def test_a_stale_declaration_is_reported():
    declared = {"OLD_SECRET": {"name": "OLD_SECRET"}}
    findings = problems({}, declared)
    assert len(findings) == 1
    assert "stale" in findings[0]


def test_post_merge_only_must_be_marked():
    derived = {"S": {"workflows": ["p.yml"], "all_post_merge_only": True}}
    declared = {"S": {"name": "S"}}
    findings = problems(derived, declared)
    assert len(findings) == 1
    assert "post_merge_only" in findings[0]


def test_a_stale_post_merge_marker_is_reported():
    """The marker must not outlive the condition that justified it."""
    derived = {"S": {"workflows": ["pr.yml"], "all_post_merge_only": False}}
    declared = {"S": {"name": "S", "post_merge_only": True}}
    findings = problems(derived, declared)
    assert len(findings) == 1
    assert "inaccurate" in findings[0]


def test_scan_reads_the_real_workflow_directory():
    derived = scan(WORKFLOWS_DIR)
    # The secret whose absence turned main red; it must be visible to the gate.
    assert "OKR_RELEASE_MANIFEST_ATTESTATION_SECRET" in derived
    assert "GITHUB_TOKEN" not in derived


def test_the_repository_declaration_matches_its_workflows():
    """If this fails, declare or remove the secret rather than editing the gate."""
    assert DECLARATION.exists(), f"{DECLARATION} is missing"
    assert problems(scan(WORKFLOWS_DIR), load_declaration(DECLARATION)) == []


def test_the_gate_exits_zero_on_the_current_repository():
    assert main([]) == 0


def test_the_gate_reports_the_post_merge_only_set(capsys):
    main([])
    output = capsys.readouterr().out
    assert "Post-merge only" in output
    assert "OKR_RELEASE_MANIFEST_ATTESTATION_SECRET" in output


def test_an_undeclared_secret_fails_a_workflow_scan(tmp_path, monkeypatch):
    """A newly referenced secret must fail the gate, which is the whole point."""
    workflow = tmp_path / "brand-new.yml"
    workflow.write_text(
        "on:\n  pull_request:\n\njobs:\n  a:\n    steps:\n"
        "      - run: echo ${{ secrets.BRAND_NEW_SECRET }}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.check_workflow_secret_prerequisites.WORKFLOWS_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.check_workflow_secret_prerequisites.DECLARATION", DECLARATION
    )
    import scripts.check_workflow_secret_prerequisites as gate

    assert gate.main([]) == 1


def test_declaration_file_is_valid_json_with_required_fields():
    import json

    payload = json.loads(
        Path(ROOT / "docs" / "deploy" / "required-secrets.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["schema_version"] == 1
    for item in payload["secrets"]:
        assert item["name"]
        assert item["purpose"], f"{item['name']} has no purpose"
        assert item["workflows"], f"{item['name']} names no workflow"
        assert isinstance(item["post_merge_only"], bool)
