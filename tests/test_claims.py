from __future__ import annotations

from llm_wiki.claims import claims_for_page_title, claims_for_pages
from llm_wiki.models import ClaimRecord, ClaimStore, PageFrontmatter, WikiPage


def make_claim(
    *,
    claim_id: str,
    source_id: str,
    source_title: str,
    related_pages: list[str],
    published_at: str | None,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        text=f"{claim_id} text",
        introduced_by_source_id=source_id,
        source_title=source_title,
        published_at=published_at,
        observed_at="2026-05-19T10:00:00+01:00",
        related_pages=related_pages,
    )


def make_page(*, title: str, source_ids: list[str]) -> WikiPage:
    return WikiPage(
        path=f"/tmp/{title}.md",
        frontmatter=PageFrontmatter(
            title=title,
            type="concept",
            updated_at="2026-05-19T10:00:00+01:00",
            source_ids=source_ids,
        ),
        body="## Concept Summary\nTest page.",
    )


def test_claim_matching_uses_page_titles_source_ids_and_deduped_ordering() -> None:
    early = make_claim(
        claim_id="early",
        source_id="source-a",
        source_title="Source A",
        related_pages=["Target Topic"],
        published_at="2024-01-01",
    )
    same_claim_via_source_id = make_claim(
        claim_id="source-match",
        source_id="source-b",
        source_title="Source B",
        related_pages=["Other Topic"],
        published_at="2025-01-01",
    )
    same_claim_duplicate = make_claim(
        claim_id="early",
        source_id="source-a",
        source_title="Source A",
        related_pages=["Target Topic"],
        published_at="2024-01-01",
    )
    source_title_match = make_claim(
        claim_id="source-title",
        source_id="source-c",
        source_title="Target Topic",
        related_pages=[],
        published_at=None,
    )
    unrelated = make_claim(
        claim_id="unrelated",
        source_id="source-d",
        source_title="Source D",
        related_pages=["Unrelated"],
        published_at="2023-01-01",
    )
    store = ClaimStore(claims=[same_claim_via_source_id, unrelated, source_title_match, early, same_claim_duplicate])
    page = make_page(title="Target Topic", source_ids=["source-b"])

    matches = claims_for_pages(store, [page])

    assert [claim.claim_id for claim in matches] == ["early", "source-match", "source-title"]

    title_matches = claims_for_page_title(store, "Target Topic", ["source-b"])

    assert [claim.claim_id for claim in title_matches] == ["early", "source-match", "source-title"]
