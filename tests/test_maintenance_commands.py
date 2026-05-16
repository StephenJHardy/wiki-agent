from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def test_refresh_source_backfills_publication_metadata_and_timelines(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/paper.md"
    source_path.write_text(
        "\n".join(
            [
                "# Provenance Paper",
                "",
                "OpenAI studies durable wiki systems.",
                "",
                "## Provenance",
                "",
                "- Provenance helps identify who introduced a claim.",
            ]
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "paper.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    registry_before = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    assert registry_before["sources"][0].get("published_at") is None

    source_path.write_text(
        "\n".join(
            [
                "# Provenance Paper",
                "",
                "Authors: Ada Lovelace and Alan Turing",
                "Published: July 11, 2025",
                "Venue: Journal of Wiki Maintenance",
                "",
                "OpenAI studies durable wiki systems.",
                "",
                "## Provenance",
                "",
                "- Provenance helps identify who introduced a claim.",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["refresh-source", "paper", "--path", str(tmp_path), "--no-llm"])

    assert result.exit_code == 0
    assert "Refreshed 1 source(s)." in result.stdout

    registry_after = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    record = registry_after["sources"][0]
    assert record["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert record["published_at"] == "2025-07-11"
    assert record["published_at_precision"] == "day"
    assert record["venue"] == "Journal of Wiki Maintenance"

    source_page = (tmp_path / "vault/wiki/sources/paper.md").read_text(encoding="utf-8")
    assert "## Source Metadata" in source_page
    assert "- Published: 2025-07-11 (day)" in source_page

    concept_page = (tmp_path / "vault/wiki/concepts/provenance.md").read_text(encoding="utf-8")
    assert "## Claim Timeline" in concept_page
    assert "2025-07-11: Ada Lovelace, Alan Turing, [[Provenance Paper]] discusses [[Provenance]]" in concept_page

    log_text = (tmp_path / "vault/wiki/log.md").read_text(encoding="utf-8")
    assert "refresh | Provenance Paper" in log_text


def test_refresh_source_all_refreshes_registered_sources(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    first = tmp_path / "vault/raw/sources/first.md"
    second = tmp_path / "vault/raw/sources/second.md"
    first.write_text("# First\n\nFirst discusses Memory.", encoding="utf-8")
    second.write_text("# Second\n\nSecond discusses Retrieval.", encoding="utf-8")

    assert runner.invoke(app, ["ingest", "first.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0
    assert runner.invoke(app, ["ingest", "second.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    result = runner.invoke(app, ["refresh-source", "--all", "--path", str(tmp_path), "--no-llm"])

    assert result.exit_code == 0
    assert "Refreshed 2 source(s)." in result.stdout
    log_text = (tmp_path / "vault/wiki/log.md").read_text(encoding="utf-8")
    assert "refresh | First" in log_text
    assert "refresh | Second" in log_text


def test_rebuild_index_restores_index_from_wiki_pages(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/retrieval.md"
    source_path.write_text("# Retrieval Systems\n\nRetrieval improves grounded answers.", encoding="utf-8")
    assert runner.invoke(app, ["ingest", "retrieval.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    index_path = tmp_path / "vault/wiki/index.md"
    index_path.write_text("# Broken Index\n", encoding="utf-8")

    result = runner.invoke(app, ["rebuild-index", "--path", str(tmp_path)])

    assert result.exit_code == 0
    index_text = index_path.read_text(encoding="utf-8")
    assert "[[Retrieval Systems]]" in index_text
    assert "rebuild-index | Wiki index" in (tmp_path / "vault/wiki/log.md").read_text(encoding="utf-8")
