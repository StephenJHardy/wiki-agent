from __future__ import annotations

from hashlib import sha1
from pathlib import Path

from .filesystem import read_json, slugify
from .models import ClaimRecord, ClaimStore, SourceAnalysis, SourceRecord, WikiPage


def load_claim_store(state_root: Path) -> ClaimStore:
    path = claims_state_path(state_root)
    if not path.exists():
        return ClaimStore()
    return ClaimStore.model_validate(read_json(path))


def claims_state_path(state_root: Path) -> Path:
    return state_root / "claims.json"


def build_claims_for_source(*, record: SourceRecord, analysis: SourceAnalysis, observed_at: str) -> list[ClaimRecord]:
    related_pages = dedupe_keep_order(analysis.entities + analysis.concepts)
    claim_texts = analysis.key_points or [analysis.summary]
    claims: list[ClaimRecord] = []
    for text in claim_texts[:8]:
        cleaned = " ".join(text.split()).strip(" -")
        if not cleaned:
            continue
        claims.append(
            ClaimRecord(
                claim_id=build_claim_id(record.source_id, cleaned),
                text=cleaned,
                introduced_by_source_id=record.source_id,
                source_title=record.title,
                published_at=record.published_at,
                published_at_precision=record.published_at_precision,
                observed_at=observed_at,
                confidence=0.75 if analysis.key_points else 0.6,
                related_pages=related_pages,
            )
        )
    return claims


def upsert_claims_for_source(*, store: ClaimStore, record: SourceRecord, analysis: SourceAnalysis, observed_at: str) -> ClaimStore:
    retained = [claim for claim in store.claims if claim.introduced_by_source_id != record.source_id]
    retained.extend(build_claims_for_source(record=record, analysis=analysis, observed_at=observed_at))
    retained.sort(key=lambda claim: ((claim.published_at or claim.observed_at), claim.source_title.lower(), claim.claim_id))
    return ClaimStore(claims=retained)


def claims_for_pages(store: ClaimStore, pages: list[WikiPage]) -> list[ClaimRecord]:
    titles = {page.frontmatter.title.casefold() for page in pages}
    source_ids = {source_id for page in pages for source_id in page.frontmatter.source_ids}
    matches = [
        claim
        for claim in store.claims
        if claim.introduced_by_source_id in source_ids
        or any(page.casefold() in titles for page in claim.related_pages)
        or claim.source_title.casefold() in titles
    ]
    return sort_claims(matches)


def claims_for_page_title(store: ClaimStore, title: str, source_ids: list[str]) -> list[ClaimRecord]:
    normalized_title = title.casefold()
    source_id_set = set(source_ids)
    matches = [
        claim
        for claim in store.claims
        if claim.introduced_by_source_id in source_id_set
        or claim.source_title.casefold() == normalized_title
        or any(page.casefold() == normalized_title for page in claim.related_pages)
    ]
    return sort_claims(matches)


def sort_claims(claims: list[ClaimRecord]) -> list[ClaimRecord]:
    deduped = {claim.claim_id: claim for claim in claims}
    return sorted(
        deduped.values(),
        key=lambda claim: ((claim.published_at or claim.observed_at), claim.source_title.lower(), claim.claim_id),
    )


def build_claim_id(source_id: str, text: str) -> str:
    digest = sha1(text.casefold().encode("utf-8")).hexdigest()[:12]
    return f"{slugify(source_id)}-{digest}"


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped
