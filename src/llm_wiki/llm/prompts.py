from __future__ import annotations

from pathlib import Path

from ..config import DEFAULT_VAULT_DIRNAME
from ..models import WikiPage
from ..schema import SchemaBundle, load_schema_bundle


def load_agent_guide(base_path: Path) -> str:
    agent_path = base_path / "AGENTS.md"
    if not agent_path.exists():
        return ""
    return agent_path.read_text(encoding="utf-8").strip()


def build_system_instruction(agent_guide: str, schema_bundle: SchemaBundle | None = None) -> str:
    base = (
        "You are maintaining a persistent markdown wiki. "
        "Prefer precise, grounded synthesis. "
        "Return structured JSON that matches the schema exactly. "
        "Do not invent files or fields. "
        "When uncertain, state uncertainty explicitly instead of fabricating detail."
    )
    sections = [base]
    if agent_guide:
        sections.append(f"Repository guide:\n{agent_guide}")
    if schema_bundle is not None:
        sections.append(schema_summary(schema_bundle))
        if schema_bundle.common_prompt:
            sections.append(f"Schema common prompt:\n{schema_bundle.common_prompt}")
    return "\n\n".join(sections)


def load_prompt_context(
    *,
    base_path: Path,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
) -> tuple[str, SchemaBundle]:
    return load_agent_guide(base_path), load_schema_bundle(base_path=base_path, vault_name=vault_name)


def build_ingest_prompt(
    *,
    source_path: str,
    source_text: str,
    index_text: str,
    recent_log_text: str,
    schema_bundle: SchemaBundle | None = None,
) -> str:
    sections = [
        "Task: analyze a new source for wiki ingestion.",
        f"Source path: {source_path}",
    ]
    if schema_bundle is not None:
        sections.append(schema_summary(schema_bundle))
        if schema_bundle.ingest_prompt:
            sections.append(f"Schema ingest prompt:\n{schema_bundle.ingest_prompt}")
        if schema_bundle.source_template:
            sections.append(f"Source page template guidance:\n{schema_bundle.source_template}")
        if schema_bundle.entity_template:
            sections.append(f"Entity page template guidance:\n{schema_bundle.entity_template}")
        if schema_bundle.concept_template:
            sections.append(f"Concept page template guidance:\n{schema_bundle.concept_template}")
    sections.extend(
        [
            "Current index:",
            index_text or "(empty)",
            "Recent log entries:",
            recent_log_text or "(empty)",
            "Source text:",
            source_text,
            (
                "Return a concise structured analysis for ingestion. "
                "Prefer stable entity and concept names, avoid duplicates, "
                "capture caveats or contradictions when present, and extract "
                "source provenance such as authors, publication date, venue, DOI, "
                "or arXiv identifier when the source provides them. "
                "Use ISO dates for published_at and set published_at_precision "
                "to day, month, or year."
            ),
        ]
    )
    return "\n\n".join(sections)


def build_query_prompt(
    *,
    question: str,
    pages: list[WikiPage],
    index_text: str,
    schema_bundle: SchemaBundle | None = None,
) -> str:
    serialized_pages = "\n\n".join(serialize_page(page) for page in pages)
    sections = [
        "Task: answer a question from the maintained wiki.",
        f"Question: {question}",
    ]
    if schema_bundle is not None:
        sections.append(schema_summary(schema_bundle))
        if schema_bundle.query_prompt:
            sections.append(f"Schema query prompt:\n{schema_bundle.query_prompt}")
        if schema_bundle.analysis_template:
            sections.append(f"Analysis page template guidance:\n{schema_bundle.analysis_template}")
    sections.extend(
        [
            "Index excerpt:",
            index_text or "(empty)",
            "Candidate pages:",
            serialized_pages or "(no pages selected)",
            (
                "Produce a direct answer grounded in the provided pages only. "
                "Call out uncertainty or thin coverage explicitly. "
                "Do not invent citations."
            ),
        ]
    )
    return "\n\n".join(sections)


def build_lint_prompt(
    *,
    pages: list[WikiPage],
    structural_findings: list[str],
    schema_bundle: SchemaBundle | None = None,
) -> str:
    serialized_pages = "\n\n".join(serialize_page(page) for page in pages)
    findings = "\n".join(f"- {finding}" for finding in structural_findings) or "- None."
    sections = ["Task: review wiki health and identify higher-order knowledge issues."]
    if schema_bundle is not None:
        sections.append(schema_summary(schema_bundle))
        if schema_bundle.lint_prompt:
            sections.append(f"Schema lint prompt:\n{schema_bundle.lint_prompt}")
    sections.extend(
        [
            "Existing structural findings:",
            findings,
            "Wiki pages:",
            serialized_pages or "(no pages)",
            (
                "Identify likely contradictions, stale claims, missing pages, "
                "missing cross references, and research gaps. "
                "Keep findings concise and actionable."
            ),
        ]
    )
    return "\n\n".join(sections)


def serialize_page(page: WikiPage) -> str:
    body = page.body.strip()
    if len(body) > 1200:
        body = body[:1200].rstrip() + "..."
    return "\n".join(
        [
            f"Title: {page.frontmatter.title}",
            f"Type: {page.frontmatter.type}",
            f"Source IDs: {', '.join(page.frontmatter.source_ids) or 'none'}",
            "Body:",
            body or "(empty)",
        ]
    )


def schema_summary(schema_bundle: SchemaBundle) -> str:
    config = schema_bundle.config
    sections = [
        f"Schema domain: {config.domain}",
        f"Schema description: {config.description}",
        f"Preferred outputs: {', '.join(config.preferred_outputs) or 'markdown'}",
        f"Frontmatter fields: {', '.join(config.frontmatter_fields)}",
    ]
    if config.required_sections:
        rendered_sections = []
        for page_type, required_sections in sorted(config.required_sections.items()):
            rendered_sections.append(f"{page_type}: {', '.join(required_sections)}")
        sections.append("Required sections by page type: " + " | ".join(rendered_sections))
    if config.prompt_versions:
        rendered_versions = ", ".join(f"{k}={v}" for k, v in sorted(config.prompt_versions.items()))
        sections.append(f"Prompt versions: {rendered_versions}")
    return "\n".join(sections)
