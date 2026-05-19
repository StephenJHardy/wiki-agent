from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .claims import claims_for_pages, load_claim_store
from .config import DEFAULT_VAULT_DIRNAME, resolve_state_root, resolve_vault_root, resolve_wiki_root
from .filesystem import read_json
from .llm import get_llm_provider
from .llm.base import LLMError
from .llm.config import load_llm_settings
from .llm.prompts import build_query_prompt, build_system_instruction, load_prompt_context
from .llm.schemas import StructuredQuerySynthesis
from .models import ClaimRecord, SourceRegistry
from .planning import ChangePlan, FileChange, OperationArtifact, OperationMetadata, apply_change_plan, save_operation_artifact
from .retrieval import RetrievalMatch, retrieve_pages
from .wiki import collect_wiki_pages, page_summary, render_analysis_page, render_index, render_log_with_entry


@dataclass(slots=True)
class RawSourceMatch:
    source_id: str
    title: str
    path: str
    score: float
    snippet: str


class QueryResult:
    def __init__(
        self,
        question: str,
        answer_markdown: str,
        matched_titles: list[str],
        written_page: Path | None,
        change_plan: ChangePlan,
        artifact_path: Path,
        dry_run: bool,
        raw_source_fallback: bool,
    ) -> None:
        self.question = question
        self.answer_markdown = answer_markdown
        self.matched_titles = matched_titles
        self.written_page = written_page
        self.change_plan = change_plan
        self.artifact_path = artifact_path
        self.dry_run = dry_run
        self.raw_source_fallback = raw_source_fallback


def run_query(
    *,
    base_path: Path,
    question: str,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    file_answer: bool = False,
    title: str | None = None,
    use_llm: bool = True,
    provider_name: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
    max_file_changes: int | None = None,
) -> QueryResult:
    wiki_root = resolve_wiki_root(base_path, vault_name)
    state_root = resolve_state_root(base_path, vault_name)
    vault_root = resolve_vault_root(base_path, vault_name)
    llm_settings = load_llm_settings(base_path=base_path, provider=provider_name, model=model)
    _, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)

    index_path = wiki_root / "index.md"
    index_text = index_path.read_text(encoding="utf-8")
    pages = collect_wiki_pages(wiki_root)
    retrieval_matches = retrieve_pages(question, pages, limit=5)
    selected_pages = [match.page for match in retrieval_matches[:3]]

    raw_source_fallback = should_trigger_raw_source_fallback(retrieval_matches)
    raw_matches = search_raw_sources(
        question=question,
        state_root=state_root,
        vault_root=vault_root,
        limit=3,
    ) if raw_source_fallback else []

    answer_markdown, llm_used = render_query_answer(
        question,
        retrieval_matches[:3],
        raw_matches=raw_matches,
        base_path=base_path,
        state_root=state_root,
        index_text=index_text,
        vault_name=vault_name,
        use_llm=use_llm,
        provider_name=provider_name,
        model=model,
    )

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = OperationMetadata(
        timestamp=timestamp,
        operation="query",
        schema_domain=schema_bundle.config.domain,
        prompt_versions=schema_bundle.config.prompt_versions,
        llm_requested=use_llm,
        llm_used=llm_used,
        llm_provider=llm_settings.provider,
        llm_model=llm_settings.model if llm_settings.enabled else None,
        raw_source_fallback=raw_source_fallback and bool(raw_matches),
        retrieval_traces=[
            {
                "title": match.page.frontmatter.title,
                "score": round(match.score, 2),
                "reasons": match.reasons,
                "snippet": match.snippet,
            }
            for match in retrieval_matches[:5]
        ],
    )

    written_page: Path | None = None
    plan = ChangePlan(operation="query", title=title or default_analysis_title(question), metadata=metadata)
    if file_answer:
        page_title = title or default_analysis_title(question)
        source_ids = collect_source_ids(selected_pages)
        written_page = wiki_root / "analyses" / f"{slugify_title(page_title)}.md"
        analysis_after = render_analysis_page(
            title=page_title,
            body=answer_markdown,
            source_ids=source_ids,
            timestamp=timestamp,
            summary=f"Filed answer for query: {question}",
            aliases=[question],
            tags=["analysis", "query"],
            related_topics=[page.frontmatter.title for page in selected_pages],
        )
        existing_pages = collect_wiki_pages(wiki_root)
        next_pages = [page for page in existing_pages if Path(page.path) != written_page]
        next_pages.append(page_from_content(written_page, analysis_after))
        index_after = render_index(wiki_root=wiki_root, pages=next_pages)
        detail_lines = [
            f"- Question: {question}",
            f"- Filed answer: `{written_page.relative_to(wiki_root).as_posix()}`",
            f"- Referenced pages: {', '.join(f'[[{page.frontmatter.title}]]' for page in selected_pages) or 'none'}",
        ]
        if raw_source_fallback and raw_matches:
            detail_lines.append(
                "- Raw-source fallback: "
                + ", ".join(f"`{match.path}`" for match in raw_matches)
            )
        detail_lines.extend(operation_metadata_lines(metadata))
        existing_log = (wiki_root / "log.md").read_text(encoding="utf-8").rstrip()
        log_after = render_log_with_entry(
            existing=existing_log,
            operation="query",
            title=page_title,
            detail_lines=detail_lines,
        )
        plan = ChangePlan(
            operation="query",
            title=page_title,
            metadata=metadata,
            detail_lines=detail_lines,
            changes=build_changes(
                [
                    (written_page, analysis_after),
                    (wiki_root / "index.md", index_after),
                    (wiki_root / "log.md", log_after),
                ]
            ),
        )
        plan.validate(max_file_changes=max_file_changes)
        if not dry_run:
            apply_change_plan(plan)

    artifact_path = save_operation_artifact(
        state_root=state_root,
        artifact=OperationArtifact(
            metadata=metadata,
            details={
                "question": question,
                "matched_titles": [page.frontmatter.title for page in selected_pages],
                "claim_ids": [
                    claim.claim_id
                    for claim in claims_for_pages(load_claim_store(state_root), selected_pages)
                ],
                "raw_source_matches": [match.__dict__ for match in raw_matches],
            },
            change_summary={
                "filed": file_answer,
                "file_changes": len(plan.changed_files()),
                "dry_run": dry_run,
            },
        ),
    )

    return QueryResult(
        question=question,
        answer_markdown=answer_markdown,
        matched_titles=[page.frontmatter.title for page in selected_pages],
        written_page=written_page,
        change_plan=plan,
        artifact_path=artifact_path,
        dry_run=dry_run,
        raw_source_fallback=raw_source_fallback and bool(raw_matches),
    )


def render_query_answer(
    question: str,
    matches: list[RetrievalMatch],
    *,
    raw_matches: list[RawSourceMatch],
    base_path: Path,
    state_root: Path,
    index_text: str,
    vault_name: str,
    use_llm: bool,
    provider_name: str | None,
    model: str | None,
) -> tuple[str, bool]:
    if not matches and not raw_matches:
        return (
            "\n".join(
                [
                    "# Query Result",
                    "",
                    f"Question: {question}",
                    "",
                    "## Answer",
                    "The current wiki does not contain enough relevant material to answer this yet.",
                    "",
                    "## Next Steps",
                    "- Ingest a source that directly addresses the question.",
                    "- Check whether the relevant concept or entity page is missing.",
                ]
            ),
            False,
        )

    pages = [match.page for match in matches]
    provenance_claims = claims_for_pages(load_claim_store(state_root), pages)
    llm_synthesis = synthesize_query_with_llm(
        question=question,
        pages=pages,
        base_path=base_path,
        index_text=index_text,
        vault_name=vault_name,
        use_llm=use_llm,
        provider_name=provider_name,
        model=model,
    )
    if llm_synthesis is not None and matches:
        lines = [
            "# Query Result",
            "",
            f"Question: {question}",
            "",
            "## Answer",
            llm_synthesis.answer,
        ]
        if llm_synthesis.uncertainty_notes:
            lines.extend(["", "## Uncertainty"])
            lines.extend([f"- {note}" for note in llm_synthesis.uncertainty_notes])
        if llm_synthesis.follow_up_questions:
            lines.extend(["", "## Follow-up Questions"])
            lines.extend([f"- {item}" for item in llm_synthesis.follow_up_questions])
        lines.extend(["", "## Citations"])
        lines.extend([f"- [[{page.frontmatter.title}]]" for page in pages])
        if provenance_claims:
            lines.extend(["", "## Provenance"])
            lines.extend(render_provenance_lines(provenance_claims))
        if raw_matches:
            lines.extend(["", "## Raw Source Fallback"])
            lines.extend(render_raw_source_lines(raw_matches))
        lines.extend(["", "## Retrieved Pages"])
        lines.extend(render_retrieval_lines(matches))
        return "\n".join(lines), True

    synthesis_lines = []
    if matches:
        synthesis_lines.append(
            f"Based on {', '.join(f'[[{page.frontmatter.title}]]' for page in pages)}, the current wiki suggests:"
        )
        for match in matches:
            synthesis_lines.append(f"- [[{match.page.frontmatter.title}]]: {match.snippet}")
    else:
        synthesis_lines.append("The wiki pages are too thin for a direct answer, so raw local sources were searched instead.")

    citations = [f"- [[{page.frontmatter.title}]]" for page in pages] or ["- No wiki citations available."]
    lines = [
        "# Query Result",
        "",
        f"Question: {question}",
        "",
        "## Answer",
        *synthesis_lines,
        "",
        "## Citations",
        *citations,
    ]
    if raw_matches:
        lines.extend(["", "## Raw Source Fallback"])
        lines.extend(render_raw_source_lines(raw_matches))
    if provenance_claims:
        lines.extend(["", "## Provenance"])
        lines.extend(render_provenance_lines(provenance_claims))
    if matches:
        lines.extend(["", "## Retrieved Pages"])
        lines.extend(render_retrieval_lines(matches))
    return "\n".join(lines), False


def synthesize_query_with_llm(
    *,
    question: str,
    pages: list,
    base_path: Path,
    index_text: str,
    vault_name: str,
    use_llm: bool,
    provider_name: str | None,
    model: str | None,
) -> StructuredQuerySynthesis | None:
    if not use_llm:
        return None
    provider = get_llm_provider(base_path=base_path, provider_name=provider_name, model=model)
    if provider is None:
        return None

    agent_guide, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)
    prompt = build_query_prompt(question=question, pages=pages, index_text=index_text, schema_bundle=schema_bundle)
    system_instruction = build_system_instruction(agent_guide, schema_bundle)
    try:
        structured = provider.generate_structured(
            prompt=prompt,
            schema=StructuredQuerySynthesis,
            system_instruction=system_instruction,
            temperature=0.1,
        )
    except LLMError:
        return None
    return structured


def render_retrieval_lines(matches: list[RetrievalMatch]) -> list[str]:
    lines: list[str] = []
    for match in matches:
        summary = match.page.frontmatter.summary or page_summary(match.page.body)
        reasons = ", ".join(match.reasons) if match.reasons else "matched"
        lines.append(
            f"- [[{match.page.frontmatter.title}]] "
            f"(score: {match.score:.1f}; reasons: {reasons}) - {summary}"
        )
    return lines


def render_raw_source_lines(matches: list[RawSourceMatch]) -> list[str]:
    return [
        f"- `{match.path}` (score: {match.score:.1f}) - {match.snippet}"
        for match in matches
    ]


def render_provenance_lines(claims: list[ClaimRecord]) -> list[str]:
    lines: list[str] = []
    for claim in claims[:8]:
        date_label = claim.published_at or claim.observed_at
        date_kind = "published" if claim.published_at else "observed"
        lines.append(
            f"- {claim.text} "
            f"[source: {claim.introduced_by_source_id}; {date_kind}: {date_label}; "
            f"observed: {claim.observed_at}]"
        )
    return lines


def default_analysis_title(question: str) -> str:
    condensed = re.sub(r"\s+", " ", question.strip()).rstrip("?")
    return f"Query - {condensed[:80]}"


def collect_source_ids(pages: list) -> list[str]:
    source_ids: list[str] = []
    for page in pages:
        for source_id in page.frontmatter.source_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
    return source_ids


def should_trigger_raw_source_fallback(matches: list[RetrievalMatch]) -> bool:
    if not matches:
        return True
    if len(matches) < 2:
        return True
    return matches[0].score < 12.0


def search_raw_sources(
    *,
    question: str,
    state_root: Path,
    vault_root: Path,
    limit: int = 3,
) -> list[RawSourceMatch]:
    registry = SourceRegistry.model_validate(read_json(state_root / "sources.json"))
    query_terms = tokenize(question)
    matches: list[RawSourceMatch] = []
    for record in registry.sources:
        relative_path = record.extracted_path or record.path
        source_path = vault_root / relative_path
        if not source_path.exists():
            continue
        text = source_path.read_text(encoding="utf-8", errors="replace")
        score = score_raw_source(question=question, query_terms=query_terms, title=record.title, text=text)
        if score <= 0:
            continue
        matches.append(
            RawSourceMatch(
                source_id=record.source_id,
                title=record.title,
                path=relative_path,
                score=score,
                snippet=best_raw_snippet(question=question, text=text),
            )
        )
    matches.sort(key=lambda item: (-item.score, item.title.lower()))
    return matches[:limit]


def score_raw_source(*, question: str, query_terms: set[str], title: str, text: str) -> float:
    score = 0.0
    normalized_question = normalize(question)
    normalized_title = normalize(title)
    if normalized_question and normalized_question in normalized_title:
        score += 12.0
    title_terms = tokenize(title)
    score += len(query_terms & title_terms) * 4.0
    tokens = tokenize(text)
    score += sum(1 for token in tokens if token in query_terms)
    if normalized_question and normalized_question in normalize(text[:3000]):
        score += 5.0
    return score


def best_raw_snippet(*, question: str, text: str) -> str:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    query_terms = tokenize(question)
    best_sentence = ""
    best_score = -1.0
    for sentence in sentences[:80]:
        score = 0.0
        normalized = normalize(sentence)
        if question and normalize(question) in normalized:
            score += 6.0
        score += len(query_terms & tokenize(sentence)) * 2.0
        if score > best_score:
            best_sentence = sentence
            best_score = score
    return (best_sentence or text[:220].strip())[:220]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[a-z0-9]{2,}\b", text.lower()))


def build_changes(items: list[tuple[Path, str]]) -> list[FileChange]:
    return [FileChange(path=path, before=path.read_text(encoding="utf-8") if path.exists() else None, after=after) for path, after in items]


def page_from_content(path: Path, content: str):
    from .markdown import parse_frontmatter
    from .models import PageFrontmatter, WikiPage

    frontmatter_data, body = parse_frontmatter(content)
    return WikiPage(path=str(path), frontmatter=PageFrontmatter.model_validate(frontmatter_data), body=body)


def operation_metadata_lines(metadata: OperationMetadata) -> list[str]:
    lines = ["- Operation metadata:"]
    if metadata.llm_requested:
        lines.append("  - LLM requested: yes")
        lines.append(f"  - LLM used: {'yes' if metadata.llm_used else 'no'}")
    else:
        lines.append("  - LLM requested: no")
    if metadata.llm_provider:
        lines.append(f"  - Provider: {metadata.llm_provider}")
    if metadata.llm_model:
        lines.append(f"  - Model: {metadata.llm_model}")
    if metadata.schema_domain:
        lines.append(f"  - Schema domain: {metadata.schema_domain}")
    if metadata.prompt_versions:
        rendered_versions = ", ".join(f"{name}={version}" for name, version in sorted(metadata.prompt_versions.items()))
        lines.append(f"  - Prompt versions: {rendered_versions}")
    if metadata.raw_source_fallback:
        lines.append("  - Raw-source fallback: yes")
    return lines


def slugify_title(title: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower())).strip("-")
