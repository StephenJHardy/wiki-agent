from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def test_lint_reports_broken_links_and_can_file_report(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/notes.md"
    source_path.write_text(
        "\n".join(
            [
                "# Research Notes",
                "",
                "OpenAI studies retrieval and evaluation tradeoffs in applied systems.",
                "",
                "## Retrieval",
                "",
                "- Retrieval improves grounded answers.",
            ]
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "notes.md", "--path", str(tmp_path)]).exit_code == 0

    concept_path = tmp_path / "vault/wiki/concepts/retrieval.md"
    text = concept_path.read_text(encoding="utf-8")
    concept_path.write_text(text + "\n- [[Missing Page]]\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "lint",
            "--path",
            str(tmp_path),
            "--file",
            "--title",
            "Weekly Wiki Lint",
        ],
    )

    assert result.exit_code == 0
    assert "Broken link in [[Retrieval]] -> [[Missing Page]]" in result.stdout

    report_path = tmp_path / "vault/wiki/analyses/weekly-wiki-lint.md"
    assert report_path.exists()

    index_text = (tmp_path / "vault/wiki/index.md").read_text(encoding="utf-8")
    assert "[[Weekly Wiki Lint]]" in index_text

    log_text = (tmp_path / "vault/wiki/log.md").read_text(encoding="utf-8")
    assert "lint | Weekly Wiki Lint" in log_text


def test_lint_flags_orphan_pages(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    orphan_page = tmp_path / "vault/wiki/entities/island.md"
    orphan_page.write_text(
        "\n".join(
            [
                "---",
                "title: Island",
                "type: entity",
                "updated_at: '2026-04-05T20:00:00+10:00'",
                "source_ids:",
                "- sample",
                "---",
                "",
                "## Entity Summary",
                "Island is isolated.",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lint", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "[[Island]] has no inbound links and may be orphaned." in result.stdout
