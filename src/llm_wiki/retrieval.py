from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .models import WikiPage
from .wiki import page_summary

WORD_PATTERN = re.compile(r"\b[a-z0-9]{2,}\b")
PHRASE_SPLIT_PATTERN = re.compile(r"\s+")
HEADING_PATTERN = re.compile(r"^##+\s+(.+)$", re.MULTILINE)

STOP_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "how",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


@dataclass
class RetrievalMatch:
    page: WikiPage
    score: float
    snippet: str
    reasons: list[str]


class Reranker(Protocol):
    def rerank(self, question: str, matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
        ...


class IdentityReranker:
    def rerank(self, question: str, matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
        return matches


def retrieve_pages(
    question: str,
    pages: list[WikiPage],
    *,
    limit: int = 5,
    reranker: Reranker | None = None,
) -> list[RetrievalMatch]:
    query_terms = query_tokens(question)
    normalized_question = normalize(question)
    matches: list[RetrievalMatch] = []
    for page in pages:
        match = score_page(question=normalized_question, query_terms=query_terms, page=page)
        if match is not None:
            matches.append(match)
    matches.sort(key=lambda item: (-item.score, item.page.frontmatter.title.lower()))
    reranker = reranker or IdentityReranker()
    matches = reranker.rerank(question, matches)
    return matches[:limit]


def score_page(*, question: str, query_terms: set[str], page: WikiPage) -> RetrievalMatch | None:
    title = page.frontmatter.title
    summary = page.frontmatter.summary or page_summary(page.body)
    aliases = page.frontmatter.aliases
    tags = page.frontmatter.tags
    headings = extract_headings(page.body)
    body = page.body

    score = 0.0
    reasons: list[str] = []

    normalized_title = normalize(title)
    if question and question in normalized_title:
        score += 18.0
        reasons.append("title phrase match")

    alias_phrase_matches = [alias for alias in aliases if question and question in normalize(alias)]
    if alias_phrase_matches:
        score += 14.0
        reasons.append("alias phrase match")

    title_term_matches = intersection_score(query_terms, tokenize_text(title))
    if title_term_matches:
        score += title_term_matches * 5.0
        reasons.append("title term match")

    alias_term_matches = intersection_score(query_terms, tokenize_text(" ".join(aliases)))
    if alias_term_matches:
        score += alias_term_matches * 4.0
        reasons.append("alias term match")

    tag_term_matches = intersection_score(query_terms, tokenize_text(" ".join(tags)))
    if tag_term_matches:
        score += tag_term_matches * 3.5
        reasons.append("tag match")

    heading_term_matches = intersection_score(query_terms, tokenize_text(" ".join(headings)))
    if heading_term_matches:
        score += heading_term_matches * 3.0
        reasons.append("heading match")

    summary_term_matches = intersection_score(query_terms, tokenize_text(summary))
    if summary_term_matches:
        score += summary_term_matches * 2.5
        reasons.append("summary match")

    body_term_matches = frequency_score(query_terms, tokenize_list(body))
    if body_term_matches:
        score += min(body_term_matches, 8) * 1.0
        reasons.append("body match")

    phrase_hits = phrase_score(question, [summary, body, *headings])
    if phrase_hits:
        score += phrase_hits * 4.0
        reasons.append("body phrase match")

    score += page_type_bonus(page.frontmatter.type)

    if page.frontmatter.confidence is not None:
        score += max(min(page.frontmatter.confidence, 1.0), 0.0)

    if score <= 0:
        return None

    snippet = best_snippet(question=question, page=page, summary=summary)
    return RetrievalMatch(
        page=page,
        score=score,
        snippet=snippet,
        reasons=dedupe_keep_order(reasons),
    )


def query_tokens(question: str) -> set[str]:
    return {token for token in tokenize_text(question) if token not in STOP_TERMS}


def normalize(text: str) -> str:
    return " ".join(PHRASE_SPLIT_PATTERN.split(text.strip().lower()))


def tokenize_text(text: str) -> set[str]:
    return set(tokenize_list(text))


def tokenize_list(text: str) -> list[str]:
    return WORD_PATTERN.findall(text.lower())


def extract_headings(body: str) -> list[str]:
    return [match.group(1).strip() for match in HEADING_PATTERN.finditer(body)]


def intersection_score(query_terms: set[str], field_terms: set[str]) -> int:
    return len(query_terms & field_terms)


def frequency_score(query_terms: set[str], tokens: list[str]) -> int:
    return sum(1 for token in tokens if token in query_terms)


def phrase_score(question: str, fields: list[str]) -> int:
    if not question:
        return 0
    return sum(1 for field in fields if question in normalize(field))


def page_type_bonus(page_type: str) -> float:
    bonuses = {
        "overview": 2.5,
        "concept": 2.0,
        "entity": 1.5,
        "analysis": 1.0,
        "source": 0.5,
    }
    return bonuses.get(page_type, 0.0)


def best_snippet(*, question: str, page: WikiPage, summary: str) -> str:
    candidates = [summary, *extract_section_snippets(page.body)]
    scored_candidates: list[tuple[float, str]] = []
    query_terms = query_tokens(question)
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        score = 0.0
        if question and question in normalize(normalized):
            score += 6.0
        score += intersection_score(query_terms, tokenize_text(normalized)) * 2.0
        if score > 0:
            scored_candidates.append((score, normalized))
    if not scored_candidates:
        return summary
    scored_candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return scored_candidates[0][1][:220]


def extract_section_snippets(body: str) -> list[str]:
    sentences: list[str] = []
    active_heading = ""
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            active_heading = stripped.lstrip("#").strip()
            continue
        line = stripped.lstrip("-").strip()
        parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            normalized = part.strip()
            if normalized:
                if active_heading:
                    sentences.append(f"{active_heading}: {normalized}")
                else:
                    sentences.append(normalized)
    return sentences


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output
