from __future__ import annotations

from pathlib import Path

from scripts import check_docs_hq_links


def _configure_repository(
    monkeypatch,
    root: Path,
    *,
    readme: str,
    documents: dict[str, str],
) -> None:
    readme_path = root / "README.md"
    readme_path.write_text(readme, encoding="utf-8")

    tracked_files = [readme_path]
    for relative_path, content in documents.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        tracked_files.append(path)

    monkeypatch.setattr(check_docs_hq_links, "ROOT", root)
    monkeypatch.setattr(check_docs_hq_links, "ROOT_README", readme_path)
    monkeypatch.setattr(
        check_docs_hq_links,
        "_tracked_markdown_files",
        lambda: tracked_files,
    )


def test_rejects_competing_production_readiness_verdict(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _configure_repository(
        monkeypatch,
        tmp_path,
        readme=(
            "## Documentation HQ\n"
            "- Canonical readiness verdict: "
            "[audit](docs/PRODUCTIONIZATION_AUDIT.md)\n"
        ),
        documents={
            "docs/PRODUCTIONIZATION_AUDIT.md": (
                "Documentation HQ: [README](../README.md)\n"
                "# Production Readiness Audit\n"
                "Readiness classification: **production risky**.\n"
            ),
            "docs/SECOND_READINESS_REPORT.md": (
                "Documentation HQ: [README](../README.md)\n"
                "# Production Readiness Report\n"
                "**Verdict: Production-ready**.\n"
            ),
        },
    )

    result = check_docs_hq_links.validate()

    assert result == 1
    output = capsys.readouterr().out
    assert (
        "docs/SECOND_READINESS_REPORT.md: competing production-readiness "
        "verdict document" in output
    )


def test_rejects_readme_without_one_canonical_readiness_link(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _configure_repository(
        monkeypatch,
        tmp_path,
        readme="## Documentation HQ\n- Architecture: [docs](docs/ARCHITECTURE.md)\n",
        documents={
            "docs/PRODUCTIONIZATION_AUDIT.md": (
                "Documentation HQ: [README](../README.md)\n"
                "# Production Readiness Audit\n"
                "Production readiness score: **3.0 / 5**.\n"
            ),
        },
    )

    result = check_docs_hq_links.validate()

    assert result == 1
    output = capsys.readouterr().out
    assert "README.md must link exactly once to the canonical readiness verdict" in output
