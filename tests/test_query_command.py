from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def test_query_answers_from_wiki_and_can_file_analysis(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/retrieval.md"
    source_path.write_text(
        "\n".join(
            [
                "# Retrieval Systems",
                "",
                "Retrieval helps grounded answers when a system needs current or external knowledge.",
                "OpenAI uses evaluation discipline to decide when retrieval improves outcomes.",
                "",
                "## Retrieval",
                "",
                "- Retrieval improves grounded answers for external knowledge tasks.",
            ]
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "retrieval.md", "--path", str(tmp_path)]).exit_code == 0

    result = runner.invoke(
        app,
        [
            "query",
            "When does retrieval help?",
            "--path",
            str(tmp_path),
            "--file",
            "--title",
            "Retrieval Brief",
        ],
    )

    assert result.exit_code == 0
    assert "[[Retrieval]]" in result.stdout
    assert "[[Retrieval Systems]]" in result.stdout

    analysis_path = tmp_path / "vault/wiki/analyses/retrieval-brief.md"
    assert analysis_path.exists()
    analysis_text = analysis_path.read_text(encoding="utf-8")
    assert "type: analysis" in analysis_text
    assert "Question: When does retrieval help?" in analysis_text

    index_text = (tmp_path / "vault/wiki/index.md").read_text(encoding="utf-8")
    assert "[[Retrieval Brief]]" in index_text

    log_text = (tmp_path / "vault/wiki/log.md").read_text(encoding="utf-8")
    assert "query | Retrieval Brief" in log_text


def test_query_reports_when_wiki_is_insufficient(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    result = runner.invoke(app, ["query", "What is Vannevar Bush's Memex?", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "does not contain enough relevant material" in result.stdout
