from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app
from llm_wiki.llm.prompts import build_ingest_prompt, build_query_prompt, build_system_instruction, load_prompt_context
from llm_wiki.models import PageFrontmatter, WikiPage
from llm_wiki.schema import load_schema_bundle

runner = CliRunner()


def test_init_supports_domain_scaffolding(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path), "--domain", "research"])

    assert result.exit_code == 0
    config_text = (tmp_path / "vault/schema/config.yaml").read_text(encoding="utf-8")
    assert "domain: research" in config_text
    query_prompt_text = (tmp_path / "vault/schema/prompts/query.md").read_text(encoding="utf-8")
    assert "synthesis" in query_prompt_text.lower()


def test_load_schema_bundle_reads_prompt_fragments(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path), "--domain", "personal"]).exit_code == 0

    schema = load_schema_bundle(base_path=tmp_path)

    assert schema.config.domain == "personal"
    assert "goals" in schema.config.description.lower() or "goals" in schema.ingest_prompt.lower()
    assert schema.common_prompt
    assert schema.analysis_template


def test_prompts_include_schema_context(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path), "--domain", "research"]).exit_code == 0
    agent_guide, schema_bundle = load_prompt_context(base_path=tmp_path)
    system_instruction = build_system_instruction(agent_guide, schema_bundle)

    page = WikiPage(
        path="/tmp/sample.md",
        frontmatter=PageFrontmatter(
            title="Evaluation",
            type="concept",
            updated_at="2026-04-05T00:00:00+00:00",
            source_ids=["sample"],
            summary="Evaluation summary",
        ),
        body="## Concept Summary\nEvaluation tracks evidence quality.",
    )
    ingest_prompt = build_ingest_prompt(
        source_path="note.md",
        source_text="A note about evidence and uncertainty.",
        index_text="[[Evaluation]]",
        recent_log_text="## [2026-04-05] ingest | Sample",
        schema_bundle=schema_bundle,
    )
    query_prompt = build_query_prompt(
        question="How should evaluation work?",
        pages=[page],
        index_text="[[Evaluation]]",
        schema_bundle=schema_bundle,
    )

    assert "Schema domain: research" in system_instruction
    assert "Required sections by page type" in system_instruction
    assert "Schema ingest prompt" in ingest_prompt
    assert "Source page template guidance" in ingest_prompt
    assert "Schema query prompt" in query_prompt
