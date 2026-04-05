from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app
from llm_wiki.llm.schemas import StructuredIngestAnalysis, StructuredLintReview, StructuredQuerySynthesis

runner = CliRunner()


class FakeProvider:
    def __init__(self, response: object) -> None:
        self.response = response

    def generate_structured(self, **_: object) -> object:
        return self.response


def test_ingest_uses_llm_provider_when_available(monkeypatch, tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/llm.md"
    source_path.write_text("# Placeholder\n\nThis source should be replaced by LLM analysis.", encoding="utf-8")

    monkeypatch.setattr(
        "llm_wiki.ingest.get_llm_provider",
        lambda **_: FakeProvider(
            StructuredIngestAnalysis(
                title="LLM Driven Source",
                summary="A model-generated summary.",
                key_points=["Point one"],
                entities=["Gemini"],
                concepts=["Structured Output"],
                caveats=["Needs review"],
            )
        ),
    )

    result = runner.invoke(app, ["ingest", "llm.md", "--path", str(tmp_path), "--llm"])

    assert result.exit_code == 0
    source_page = (tmp_path / "vault/wiki/sources/llm.md").read_text(encoding="utf-8")
    assert "LLM Driven Source" in source_page
    assert "[[Gemini]]" in source_page
    assert "[[Structured Output]]" in source_page


def test_query_uses_llm_provider_when_available(monkeypatch, tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/query.md"
    source_path.write_text("# Query Source\n\nRetrieval helps grounded answers.", encoding="utf-8")
    assert runner.invoke(app, ["ingest", "query.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    monkeypatch.setattr(
        "llm_wiki.query.get_llm_provider",
        lambda **_: FakeProvider(
            StructuredQuerySynthesis(
                answer="LLM-backed answer.",
                uncertainty_notes=["Only one source is available."],
                follow_up_questions=["What other sources should be added?"],
            )
        ),
    )

    result = runner.invoke(app, ["query", "When does retrieval help?", "--path", str(tmp_path), "--llm"])

    assert result.exit_code == 0
    assert "LLM-backed answer." in result.stdout
    assert "Only one source is available." in result.stdout


def test_lint_uses_llm_provider_when_available(monkeypatch, tmp_path: Path) -> None:
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

    monkeypatch.setattr(
        "llm_wiki.lint.get_llm_provider",
        lambda **_: FakeProvider(
            StructuredLintReview(
                contradictions=["Island may conflict with another geography page."],
                stale_claims=[],
                missing_pages=["Archipelago"],
                missing_cross_references=["Island should link to Coastline."],
                research_gaps=["Need a source describing Island's context."],
            )
        ),
    )

    result = runner.invoke(app, ["lint", "--path", str(tmp_path), "--llm"])

    assert result.exit_code == 0
    assert "Possible contradiction: Island may conflict with another geography page." in result.stdout
    assert "Missing page: Archipelago" in result.stdout
