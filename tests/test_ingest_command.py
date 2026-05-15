from __future__ import annotations

import json
from pathlib import Path

import pymupdf
from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def test_ingest_creates_source_pages_and_registry(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    source_path = tmp_path / "vault/raw/sources/attention.md"
    source_path.write_text(
        "\n".join(
            [
                "# Attention and Memory",
                "",
                "Authors: Ada Lovelace and Alan Turing",
                "Published: May 17, 2024",
                "DOI: 10.1234/example.doi",
                "",
                "Attention shapes how Memory is encoded in learning systems.",
                "OpenAI and Anthropic both discuss evaluation discipline in applied LLM work.",
                "",
                "## Retrieval",
                "",
                "- Retrieval can improve grounded answers.",
                "- However, repeated retrieval alone does not create durable synthesis.",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["ingest", "attention.md", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / "vault/wiki/sources/attention.md").exists()
    assert (tmp_path / "vault/wiki/entities/openai.md").exists()
    assert (tmp_path / "vault/wiki/concepts/retrieval.md").exists()

    registry = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    assert registry["sources"][0]["source_id"] == "attention"
    assert registry["sources"][0]["title"] == "Attention and Memory"
    assert registry["sources"][0]["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert registry["sources"][0]["published_at"] == "2024-05-17"
    assert registry["sources"][0]["published_at_precision"] == "day"
    assert registry["sources"][0]["doi"] == "10.1234/example.doi"

    source_page = (tmp_path / "vault/wiki/sources/attention.md").read_text(encoding="utf-8")
    assert "type: source" in source_page
    assert "authors:" in source_page
    assert "published_at: '2024-05-17'" in source_page
    assert "## Source Metadata" in source_page
    assert "- Authors: Ada Lovelace, Alan Turing" in source_page
    assert "[[OpenAI]]" in source_page
    assert "[[Retrieval]]" in source_page

    concept_page = (tmp_path / "vault/wiki/concepts/retrieval.md").read_text(encoding="utf-8")
    assert "## Claim Timeline" in concept_page
    assert "2024-05-17: Ada Lovelace, Alan Turing, [[Attention and Memory]] discusses [[Retrieval]]" in concept_page

    index_page = (tmp_path / "vault/wiki/index.md").read_text(encoding="utf-8")
    assert "[[Attention and Memory]]" in index_page
    assert "[[OpenAI]]" in index_page
    assert "[[Retrieval]]" in index_page

    log_page = (tmp_path / "vault/wiki/log.md").read_text(encoding="utf-8")
    assert "ingest | Attention and Memory" in log_page
    assert "`sources/attention.md`" in log_page


def test_ingest_reuses_existing_topic_pages_and_updates_registry(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    source_path = tmp_path / "vault/raw/sources/company-notes.txt"
    source_path.write_text(
        "OpenAI builds tools for research teams. Evaluation practice matters for durable systems.",
        encoding="utf-8",
    )

    first_result = runner.invoke(app, ["ingest", "company-notes.txt", "--path", str(tmp_path)])
    assert first_result.exit_code == 0

    source_path.write_text(
        "OpenAI builds tools for research teams. Evaluation practice matters for durable systems, "
        "but deployment pressure can hide weak assumptions.",
        encoding="utf-8",
    )
    second_result = runner.invoke(app, ["ingest", "company-notes.txt", "--path", str(tmp_path)])
    assert second_result.exit_code == 0

    registry = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    assert len(registry["sources"]) == 1

    entity_page = (tmp_path / "vault/wiki/entities/openai.md").read_text(encoding="utf-8")
    assert entity_page.count("- Company Notes: referenced in [[Company Notes]]") == 1
    assert entity_page.count("- [[Company Notes]]") == 1

    source_page = (tmp_path / "vault/wiki/sources/company-notes.md").read_text(encoding="utf-8")
    assert "deployment pressure can hide weak assumptions" in source_page


def test_ingest_pdf_creates_derived_markdown_and_preserves_raw_source(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    source_path = tmp_path / "vault/raw/sources/transformers.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Transformers for Sequence Models\n\nTransformers improve sequence modeling with attention.",
    )
    document.save(source_path)
    document.close()

    result = runner.invoke(app, ["ingest", "transformers.pdf", "--path", str(tmp_path), "--no-llm"])

    assert result.exit_code == 0
    assert source_path.exists()
    assert (tmp_path / "vault/wiki/sources/transformers-pdf.md").exists()
    extracted_path = tmp_path / "vault/state/extracted/transformers-pdf.md"
    assert extracted_path.exists()

    extracted_text = extracted_path.read_text(encoding="utf-8")
    assert "Transformers" in extracted_text

    registry = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    record = registry["sources"][0]
    assert record["file_type"] == "pdf"
    assert record["path"] == "raw/sources/transformers.pdf"
    assert record["extracted_path"] == "state/extracted/transformers-pdf.md"

    source_page = (tmp_path / "vault/wiki/sources/transformers-pdf.md").read_text(encoding="utf-8")
    assert "source_path: raw/sources/transformers.pdf" in source_page
    assert "derived_path: state/extracted/transformers-pdf.md" in source_page


def test_ingest_url_snapshots_html_locally_before_ingesting(tmp_path: Path, monkeypatch) -> None:
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    def fake_download_remote_source(url: str) -> tuple[bytes, str | None, str]:
        html = b"""
        <html>
          <head><title>Paper</title></head>
          <body>
            <article>
              <h1>Attention Paper</h1>
              <p>Attention improves sequence modeling.</p>
            </article>
          </body>
        </html>
        """
        return html, "text/html", url

    monkeypatch.setattr("llm_wiki.source_loader.download_remote_source", fake_download_remote_source)

    result = runner.invoke(
        app,
        ["ingest", "https://example.com/papers/attention", "--path", str(tmp_path), "--no-llm"],
    )

    assert result.exit_code == 0

    raw_sources = list((tmp_path / "vault/raw/sources").glob("*.html"))
    assert len(raw_sources) == 1
    raw_snapshot = raw_sources[0]
    assert "example-com-papers-attention" in raw_snapshot.name

    extracted_paths = list((tmp_path / "vault/state/extracted").glob("*.md"))
    assert len(extracted_paths) == 1
    assert "Attention Paper" in extracted_paths[0].read_text(encoding="utf-8")

    registry = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    record = registry["sources"][0]
    assert record["file_type"] == "html"
    assert record["original_url"] == "https://example.com/papers/attention"
    assert record["path"].startswith("raw/sources/example-com-papers-attention-")
    assert record["extracted_path"].startswith("state/extracted/example-com-papers-attention-")

    source_page = (tmp_path / f"vault/wiki/sources/{record['source_id']}.md").read_text(encoding="utf-8")
    assert "Original URL: https://example.com/papers/attention" in source_page


def test_ingest_dry_run_does_not_write_wiki_changes(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    source_path = tmp_path / "vault/raw/sources/dry-run.md"
    source_path.write_text("# Dry Run\n\nThis should not be written into the wiki on dry run.", encoding="utf-8")

    result = runner.invoke(app, ["ingest", "dry-run.md", "--path", str(tmp_path), "--no-llm", "--dry-run"])

    assert result.exit_code == 0
    assert not (tmp_path / "vault/wiki/sources/dry-run.md").exists()
    operations = list((tmp_path / "vault/state/operations").glob("*.json"))
    assert operations


def test_ingest_dir_copies_supported_files_into_raw_sources_and_ingests(tmp_path: Path) -> None:
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0

    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    (papers_dir / "paper-a.md").write_text("# Paper A\n\nAttention improves sequence modeling.", encoding="utf-8")
    (papers_dir / "paper-b.txt").write_text("Evaluation discipline matters for durable systems.", encoding="utf-8")
    (papers_dir / "notes.png").write_bytes(b"not-a-real-image")

    result = runner.invoke(app, ["ingest-dir", str(papers_dir), "--path", str(tmp_path), "--no-llm"])

    assert result.exit_code == 0
    assert (tmp_path / "vault/raw/sources/paper-a.md").exists()
    assert (tmp_path / "vault/raw/sources/paper-b.txt").exists()
    assert not (tmp_path / "vault/raw/sources/notes.png").exists()
    assert (tmp_path / "vault/wiki/sources/paper-a.md").exists()
    assert (tmp_path / "vault/wiki/sources/paper-b.md").exists()

    registry = json.loads((tmp_path / "vault/state/sources.json").read_text(encoding="utf-8"))
    assert len(registry["sources"]) == 2
