from __future__ import annotations

import json
from pathlib import Path

from llm_wiki.models import PageFrontmatter, WikiPage
from llm_wiki.retrieval import retrieve_pages


def make_page(
    *,
    title: str,
    page_type: str,
    body: str,
    summary: str | None = None,
    aliases: list[str] | None = None,
    tags: list[str] | None = None,
) -> WikiPage:
    return WikiPage(
        path=f"/tmp/{title}.md",
        frontmatter=PageFrontmatter(
            title=title,
            type=page_type,  # type: ignore[arg-type]
            updated_at="2026-04-05T00:00:00+00:00",
            source_ids=["sample"],
            summary=summary,
            aliases=aliases or [],
            tags=tags or [],
        ),
        body=body,
    )


def test_retrieve_pages_prefers_alias_matches() -> None:
    pages = [
        make_page(
            title="Retrieval Augmented Generation",
            page_type="concept",
            summary="A concept page about retrieval augmented generation.",
            aliases=["RAG"],
            body="## Concept Summary\nRetrieval Augmented Generation combines retrieval and generation.",
        ),
        make_page(
            title="Random Notes",
            page_type="analysis",
            body="## Notes\nThis mentions retrieval once.",
        ),
    ]

    matches = retrieve_pages("What is RAG?", pages, limit=2)

    assert matches
    assert matches[0].page.frontmatter.title == "Retrieval Augmented Generation"
    assert "alias phrase match" in matches[0].reasons or "alias term match" in matches[0].reasons


def test_retrieve_pages_uses_heading_and_summary_signals() -> None:
    pages = [
        make_page(
            title="Evaluation Practice",
            page_type="concept",
            summary="Covers evaluation discipline for LLM systems.",
            body="## Evaluation Discipline\nMeasure systems before deployment.",
        ),
        make_page(
            title="Deployment Notes",
            page_type="source",
            summary="General deployment notes.",
            body="## Misc\nNothing about evaluation here.",
        ),
    ]

    matches = retrieve_pages("How should evaluation discipline work?", pages, limit=2)

    assert matches
    assert matches[0].page.frontmatter.title == "Evaluation Practice"
    assert any(reason in matches[0].reasons for reason in ["heading match", "summary match", "title term match"])


def test_retrieval_benchmark_fixture_cases() -> None:
    fixture_path = Path(__file__).parent / "fixtures/queries/retrieval_cases.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    pages = [
        make_page(
            title="Retrieval Augmented Generation",
            page_type="concept",
            summary="A concept page about retrieval augmented generation.",
            aliases=["RAG"],
            body="## Concept Summary\nRetrieval Augmented Generation combines retrieval and generation.",
        ),
        make_page(
            title="Evaluation Practice",
            page_type="concept",
            summary="Covers evaluation discipline for LLM systems.",
            body="## Evaluation Discipline\nMeasure systems before deployment.",
        ),
        make_page(
            title="Deployment Notes",
            page_type="source",
            summary="General deployment notes.",
            body="## Misc\nNothing about evaluation here.",
        ),
    ]

    for case in cases:
        matches = retrieve_pages(case["question"], pages, limit=3)
        assert matches
        assert matches[0].page.frontmatter.title == case["expected_top_title"]
