from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from .config import DEFAULT_VAULT_DIRNAME, WIKI_SECTION_DIRECTORY, resolve_state_root, resolve_wiki_root
from .filesystem import read_json, render_json, slugify
from .llm import get_llm_provider
from .llm.base import LLMError
from .llm.config import LLMSettings, load_llm_settings
from .llm.prompts import build_ingest_prompt, build_system_instruction, load_prompt_context
from .llm.schemas import StructuredIngestAnalysis
from .markdown import load_page, parse_frontmatter, render_page
from .models import PageFrontmatter, SourceAnalysis, SourceRecord, SourceRegistry, WikiPage
from .planning import ChangePlan, FileChange, OperationArtifact, OperationMetadata, apply_change_plan, save_operation_artifact
from .source_loader import prepare_source
from .wiki import collect_wiki_pages, render_index, render_log_with_entry, unique_relative_paths

STOPWORDS = {
    "a",
    "about",
    "all",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "could",
    "do",
    "for",
    "from",
    "had",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "more",
    "most",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "who",
    "will",
    "with",
    "you",
    "your",
}
ENTITY_STOPWORDS = {
    "A",
    "An",
    "And",
    "As",
    "At",
    "But",
    "By",
    "For",
    "From",
    "He",
    "Her",
    "His",
    "If",
    "In",
    "It",
    "Its",
    "No",
    "On",
    "Or",
    "Our",
    "She",
    "The",
    "Their",
    "There",
    "They",
    "This",
    "Those",
    "We",
    "What",
    "When",
    "Where",
    "Which",
    "Who",
}
CAVEAT_MARKERS = ("however", "but", "although", "despite", "yet", "unless", "while")


class IngestResult:
    def __init__(
        self,
        source_record: SourceRecord,
        source_page_path: Path,
        updated_pages: list[Path],
        analysis: SourceAnalysis,
        change_plan: ChangePlan,
        artifact_path: Path,
        dry_run: bool,
    ) -> None:
        self.source_record = source_record
        self.source_page_path = source_page_path
        self.updated_pages = updated_pages
        self.analysis = analysis
        self.change_plan = change_plan
        self.artifact_path = artifact_path
        self.dry_run = dry_run


def ingest_source(
    base_path: Path,
    source_arg: str,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    *,
    use_llm: bool = True,
    provider_name: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
    max_file_changes: int | None = None,
) -> IngestResult:
    wiki_root = resolve_wiki_root(base_path, vault_name)
    state_root = resolve_state_root(base_path, vault_name)
    prepared_source = prepare_source(base_path, source_arg, vault_name)
    llm_settings = load_llm_settings(base_path=base_path, provider=provider_name, model=model)
    _, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)

    now = datetime.now().astimezone()
    timestamp = now.isoformat(timespec="seconds")
    date_stamp = now.date().isoformat()

    registry_path = state_root / "sources.json"
    registry = SourceRegistry.model_validate(read_json(registry_path))
    analysis, llm_used = analyze_source(
        prepared_source.source_path,
        prepared_source.source_text,
        base_path=base_path,
        vault_name=vault_name,
        use_llm=use_llm,
        provider_name=provider_name,
        model=model,
    )

    existing = next((record for record in registry.sources if record.source_id == prepared_source.source_id), None)
    ingested_at = existing.ingested_at if existing else timestamp
    record = SourceRecord(
        source_id=prepared_source.source_id,
        title=analysis.title,
        path=prepared_source.relative_source_path,
        checksum=prepared_source.checksum,
        file_type=prepared_source.file_type,
        extracted_path=prepared_source.extracted_path,
        original_url=prepared_source.original_url,
        ingested_at=ingested_at,
        updated_at=timestamp,
    )
    registry = upsert_source_record(registry, record)

    planned_pages: list[tuple[Path, str]] = []
    source_page_path, source_page_content = build_source_page(
        wiki_root=wiki_root,
        analysis=analysis,
        record=record,
        timestamp=timestamp,
    )
    planned_pages.append((source_page_path, source_page_content))

    for entity in analysis.entities:
        planned_pages.append(
            build_topic_page(
                wiki_root=wiki_root,
                page_type="entity",
                title=entity,
                record=record,
                summary_line=f"- {analysis.title}: referenced in [[{analysis.title}]]",
                timestamp=timestamp,
            )
        )

    for concept in analysis.concepts:
        planned_pages.append(
            build_topic_page(
                wiki_root=wiki_root,
                page_type="concept",
                title=concept,
                record=record,
                summary_line=f"- {analysis.title}: discussed in [[{analysis.title}]]",
                timestamp=timestamp,
            )
        )

    current_pages = collect_wiki_pages(wiki_root)
    page_map = {Path(page.path): page for page in current_pages}
    planned_paths = {path for path, _ in planned_pages}
    next_pages = [page for path, page in page_map.items() if path not in planned_paths]
    next_pages.extend([page_from_content(path, content) for path, content in planned_pages])
    index_after = render_index(wiki_root=wiki_root, pages=next_pages)

    updated_pages = [path for path, _ in planned_pages]
    detail_lines = [
        "- Updated pages:",
        *[f"  - `{relative_path}`" for relative_path in unique_relative_paths(wiki_root, updated_pages)],
        f"- Raw source: `{record.path}`",
    ]
    if record.extracted_path is not None:
        detail_lines.append(f"- Extracted text: `{record.extracted_path}`")
    if record.original_url is not None:
        detail_lines.append(f"- Original URL: {record.original_url}")
    if analysis.caveats:
        detail_lines.append("- Caveats detected:")
        detail_lines.extend([f"  - {caveat}" for caveat in analysis.caveats])
    else:
        detail_lines.append("- Caveats detected: none")

    metadata = OperationMetadata(
        timestamp=timestamp,
        operation="ingest",
        schema_domain=schema_bundle.config.domain,
        prompt_versions=schema_bundle.config.prompt_versions,
        llm_requested=use_llm,
        llm_used=llm_used,
        llm_provider=llm_settings.provider,
        llm_model=llm_settings.model if llm_settings.enabled else None,
        notes=build_operation_notes(llm_settings=llm_settings, llm_used=llm_used),
    )
    detail_lines.extend(operation_metadata_lines(metadata))

    existing_log = (wiki_root / "log.md").read_text(encoding="utf-8").rstrip()
    log_after = render_log_with_entry(
        existing=existing_log,
        operation="ingest",
        title=analysis.title,
        detail_lines=detail_lines,
        date_stamp=date_stamp,
    )

    plan = ChangePlan(
        operation="ingest",
        title=analysis.title,
        metadata=metadata,
        detail_lines=detail_lines,
        changes=build_changes(
            [
                (registry_path, render_json(registry.model_dump())),
                *planned_pages,
                (wiki_root / "index.md", index_after),
                (wiki_root / "log.md", log_after),
            ]
        ),
    )
    plan.validate(max_file_changes=max_file_changes)

    artifact_path = save_operation_artifact(
        state_root=state_root,
        artifact=OperationArtifact(
            metadata=metadata,
            details={
                "source_id": record.source_id,
                "source_path": record.path,
                "extracted_path": record.extracted_path,
                "original_url": record.original_url,
                "updated_pages": [path.relative_to(wiki_root).as_posix() for path in updated_pages],
            },
            change_summary={
                "file_changes": len(plan.changed_files()),
                "dry_run": dry_run,
            },
        ),
    )

    if not dry_run:
        apply_change_plan(plan)

    return IngestResult(
        source_record=record,
        source_page_path=source_page_path,
        updated_pages=updated_pages,
        analysis=analysis,
        change_plan=plan,
        artifact_path=artifact_path,
        dry_run=dry_run,
    )


def analyze_source(
    path: Path,
    text: str,
    *,
    base_path: Path | None = None,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    use_llm: bool = True,
    provider_name: str | None = None,
    model: str | None = None,
) -> tuple[SourceAnalysis, bool]:
    llm_analysis = analyze_source_with_llm(
        path=path,
        text=text,
        base_path=base_path,
        vault_name=vault_name,
        use_llm=use_llm,
        provider_name=provider_name,
        model=model,
    )
    if llm_analysis is not None:
        return llm_analysis, True

    title = extract_title(path, text)
    plain_text = markdown_to_text(text)
    sentences = split_sentences(plain_text)
    summary = summarize(sentences, plain_text, title)
    key_points = extract_key_points(text, sentences)
    entities = extract_entities(plain_text, title)
    concepts = extract_concepts(text, plain_text, title, entities)
    caveats = extract_caveats(sentences)
    return (
        SourceAnalysis(
            title=title,
            summary=summary,
            key_points=key_points,
            entities=entities,
            concepts=concepts,
            caveats=caveats,
        ),
        False,
    )


def analyze_source_with_llm(
    *,
    path: Path,
    text: str,
    base_path: Path | None,
    vault_name: str,
    use_llm: bool,
    provider_name: str | None,
    model: str | None,
) -> SourceAnalysis | None:
    if not use_llm or base_path is None:
        return None

    provider = get_llm_provider(base_path=base_path, provider_name=provider_name, model=model)
    if provider is None:
        return None

    wiki_root = resolve_wiki_root(base_path, vault_name)
    index_text = (wiki_root / "index.md").read_text(encoding="utf-8")
    log_text = (wiki_root / "log.md").read_text(encoding="utf-8")
    recent_log_text = "\n".join(log_text.splitlines()[-20:])
    agent_guide, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)
    system_instruction = build_system_instruction(agent_guide, schema_bundle)
    prompt = build_ingest_prompt(
        source_path=path.name,
        source_text=text,
        index_text=index_text,
        recent_log_text=recent_log_text,
        schema_bundle=schema_bundle,
    )

    try:
        structured = provider.generate_structured(
            prompt=prompt,
            schema=StructuredIngestAnalysis,
            system_instruction=system_instruction,
            temperature=0.1,
        )
    except LLMError:
        return None

    return SourceAnalysis(
        title=structured.title.strip() or extract_title(path, text),
        summary=structured.summary.strip(),
        key_points=dedupe_keep_order(structured.key_points),
        entities=dedupe_keep_order(structured.entities),
        concepts=dedupe_keep_order(structured.concepts),
        caveats=dedupe_keep_order(structured.caveats),
    )


def extract_title(path: Path, text: str) -> str:
    if path.suffix.lower() == ".txt":
        return path.stem.replace("-", " ").replace("_", " ").title()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped:
            return stripped[:80].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def markdown_to_text(text: str) -> str:
    without_code = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    without_images = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", without_code)
    without_links = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", without_images)
    lines: list[str] = []
    for line in without_links.splitlines():
        cleaned = re.sub(r"[#>*_`~-]", " ", line).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned:
            lines.append(cleaned)
    return ". ".join(lines).strip()


def split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def summarize(sentences: list[str], plain_text: str, title: str) -> str:
    if sentences:
        chosen = " ".join(sentences[:2]).strip()
        return chosen[:400]
    if plain_text:
        return plain_text[:400]
    return f"Summary for {title}."


def extract_key_points(raw_text: str, sentences: list[str]) -> list[str]:
    bullet_candidates = [
        line.strip().lstrip("-*").strip()
        for line in raw_text.splitlines()
        if line.strip().startswith(("- ", "* "))
    ]
    if bullet_candidates:
        return dedupe_keep_order(bullet_candidates)[:5]
    return dedupe_keep_order(sentences[:5])[:5]


def extract_entities(plain_text: str, title: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][A-Za-z]{2,}\b(?:\s+\b[A-Z][A-Za-z]{2,}\b){0,2}", plain_text)
    entities: list[str] = []
    for match in matches:
        cleaned = match.strip()
        if cleaned in ENTITY_STOPWORDS:
            continue
        if cleaned.lower() == title.lower():
            continue
        if len(cleaned) < 3:
            continue
        entities.append(cleaned)
    return dedupe_keep_order(entities)[:6]


def extract_concepts(raw_text: str, plain_text: str, title: str, entities: list[str]) -> list[str]:
    headings = [line.lstrip("#").strip() for line in raw_text.splitlines() if line.strip().startswith("##")]
    if headings:
        return dedupe_keep_order(headings)[:6]

    entity_words = {word.lower() for entity in entities for word in entity.split()}
    tokens = re.findall(r"\b[a-z][a-z]{3,}\b", plain_text.lower())
    counts = Counter(
        token
        for token in tokens
        if token not in STOPWORDS and token not in entity_words and token != title.lower()
    )
    concepts = [token.replace("-", " ").title() for token, _ in counts.most_common(6)]
    return dedupe_keep_order(concepts)[:6]


def extract_caveats(sentences: list[str]) -> list[str]:
    caveats = [
        sentence
        for sentence in sentences
        if any(marker in sentence.lower() for marker in CAVEAT_MARKERS)
    ]
    return dedupe_keep_order(caveats)[:3]


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


def upsert_source_record(registry: SourceRegistry, record: SourceRecord) -> SourceRegistry:
    sources = [entry for entry in registry.sources if entry.source_id != record.source_id]
    sources.append(record)
    sources.sort(key=lambda entry: entry.source_id)
    return SourceRegistry(sources=sources)


def build_source_page(
    *,
    wiki_root: Path,
    analysis: SourceAnalysis,
    record: SourceRecord,
    timestamp: str,
) -> tuple[Path, str]:
    target = wiki_root / "sources" / f"{record.source_id}.md"
    frontmatter = PageFrontmatter(
        title=analysis.title,
        type="source",
        updated_at=timestamp,
        source_ids=[record.source_id],
        summary=analysis.summary,
        aliases=[record.source_id, record.title],
        tags=["source", record.file_type],
        related_topics=dedupe_keep_order(analysis.entities + analysis.concepts),
        confidence=0.8,
        last_reviewed_at=timestamp,
        source_id=record.source_id,
        source_path=record.path,
        derived_path=record.extracted_path,
        original_url=record.original_url,
        ingested_at=record.ingested_at,
    )
    sections = [
        "## Summary",
        analysis.summary,
        "",
        "## Key Points",
    ]
    if analysis.key_points:
        sections.extend([f"- {point}" for point in analysis.key_points])
    else:
        sections.append("- No key points extracted.")
    sections.extend(["", "## Entities"])
    if analysis.entities:
        sections.extend([f"- [[{entity}]]" for entity in analysis.entities])
    else:
        sections.append("- No named entities extracted.")
    sections.extend(["", "## Concepts"])
    if analysis.concepts:
        sections.extend([f"- [[{concept}]]" for concept in analysis.concepts])
    else:
        sections.append("- No concepts extracted.")
    sections.extend(["", "## Caveats"])
    if analysis.caveats:
        sections.extend([f"- {caveat}" for caveat in analysis.caveats])
    else:
        sections.append("- No caveats extracted.")
    sections.extend(["", "## Provenance", f"- Raw source: `{record.path}`"])
    if record.extracted_path is not None:
        sections.append(f"- Extracted text: `{record.extracted_path}`")
    if record.original_url is not None:
        sections.append(f"- Original URL: {record.original_url}")
    return target, render_page(frontmatter, "\n".join(sections))


def build_topic_page(
    *,
    wiki_root: Path,
    page_type: str,
    title: str,
    record: SourceRecord,
    summary_line: str,
    timestamp: str,
) -> tuple[Path, str]:
    directory = WIKI_SECTION_DIRECTORY[page_type]
    target = wiki_root / directory / f"{slugify(title)}.md"
    if target.exists():
        existing_page = load_page(target)
        source_ids = dedupe_keep_order(existing_page.frontmatter.source_ids + [record.source_id])
        body = merge_topic_body(existing_page.body, record.title, summary_line)
        aliases = dedupe_keep_order(existing_page.frontmatter.aliases + build_aliases(title))
        tags = dedupe_keep_order(existing_page.frontmatter.tags + [page_type])
        related_topics = dedupe_keep_order(existing_page.frontmatter.related_topics + [record.title])
        summary = existing_page.frontmatter.summary or topic_summary(page_type, title)
    else:
        source_ids = [record.source_id]
        body = build_new_topic_body(page_type, title, record.title, summary_line)
        aliases = build_aliases(title)
        tags = [page_type]
        related_topics = [record.title]
        summary = topic_summary(page_type, title)

    frontmatter = PageFrontmatter(
        title=title,
        type=page_type,  # type: ignore[arg-type]
        updated_at=timestamp,
        source_ids=source_ids,
        summary=summary,
        aliases=aliases,
        tags=tags,
        related_topics=related_topics,
        confidence=0.65,
        last_reviewed_at=timestamp,
    )
    return target, render_page(frontmatter, body)


def build_aliases(title: str) -> list[str]:
    aliases = [title]
    if " and " in title:
        aliases.append(title.replace(" and ", " & "))
    initials = "".join(word[0] for word in re.findall(r"[A-Za-z0-9]+", title) if word)
    if len(initials) >= 2:
        aliases.append(initials.upper())
    return dedupe_keep_order(aliases)


def topic_summary(page_type: str, title: str) -> str:
    return f"{title} is a tracked {page_type} page in this wiki."


def build_new_topic_body(page_type: str, title: str, source_title: str, summary_line: str) -> str:
    section_label = "Entity" if page_type == "entity" else "Concept"
    return "\n".join(
        [
            f"## {section_label} Summary",
            f"{title} is a tracked {page_type} in this wiki.",
            "",
            "## Sources",
            summary_line,
            "",
            "## Related Pages",
            f"- [[{source_title}]]",
        ]
    )


def merge_topic_body(existing_body: str, source_title: str, summary_line: str) -> str:
    lines = existing_body.splitlines()
    if summary_line not in lines:
        try:
            sources_index = lines.index("## Sources")
        except ValueError:
            lines.extend(["", "## Sources", summary_line])
        else:
            insert_index = sources_index + 1
            while insert_index < len(lines) and lines[insert_index].startswith("- "):
                insert_index += 1
            lines.insert(insert_index, summary_line)

    related_line = f"- [[{source_title}]]"
    if related_line not in lines:
        try:
            related_index = lines.index("## Related Pages")
        except ValueError:
            lines.extend(["", "## Related Pages", related_line])
        else:
            insert_index = related_index + 1
            while insert_index < len(lines) and lines[insert_index].startswith("- "):
                insert_index += 1
            lines.insert(insert_index, related_line)

    return "\n".join(lines).strip()


def page_from_content(path: Path, content: str) -> WikiPage:
    frontmatter_data, body = parse_frontmatter(content)
    return WikiPage(
        path=str(path),
        frontmatter=PageFrontmatter.model_validate(frontmatter_data),
        body=body,
    )


def build_changes(items: list[tuple[Path, str]]) -> list[FileChange]:
    changes: list[FileChange] = []
    for path, after in items:
        before = path.read_text(encoding="utf-8") if path.exists() else None
        changes.append(FileChange(path=path, before=before, after=after))
    return changes


def build_operation_notes(*, llm_settings: LLMSettings, llm_used: bool) -> list[str]:
    notes: list[str] = []
    if llm_settings.provider:
        notes.append(f"Provider: {llm_settings.provider}")
    if llm_settings.enabled and llm_settings.model:
        notes.append(f"Model: {llm_settings.model}")
    notes.append(f"LLM used: {'yes' if llm_used else 'no'}")
    return notes


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
    return lines
