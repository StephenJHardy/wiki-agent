from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .filesystem import slugify, write_text
from .markdown import load_page, render_page
from .models import PageFrontmatter, WikiPage

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def collect_wiki_pages(wiki_root: Path) -> list[WikiPage]:
    pages: list[WikiPage] = []
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in {"index.md", "log.md"}:
            continue
        pages.append(load_page(path))
    return pages


def page_summary(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("- "):
            return stripped[:140]
    return "No summary available."


def rebuild_index(*, wiki_root: Path, pages: list[WikiPage]) -> None:
    write_text(wiki_root / "index.md", render_index(pages=pages, wiki_root=wiki_root))


def render_index(*, pages: list[WikiPage], wiki_root: Path) -> str:
    grouped: dict[str, list[WikiPage]] = {
        "overview": [],
        "entity": [],
        "concept": [],
        "source": [],
        "analysis": [],
    }
    for page in pages:
        grouped[page.frontmatter.type].append(page)

    lines = [
        "# Index",
        "",
        "This file is the top-level catalog for the wiki.",
        "",
    ]
    for page_type, heading in (
        ("overview", "Overviews"),
        ("entity", "Entities"),
        ("concept", "Concepts"),
        ("source", "Sources"),
        ("analysis", "Analyses"),
    ):
        lines.append(f"## {heading}")
        section_pages = sorted(grouped[page_type], key=lambda page: page.frontmatter.title.lower())
        if not section_pages:
            lines.append(f"- No {page_type} pages yet.")
            lines.append("")
            continue
        for page in section_pages:
            relative_path = Path(page.path).relative_to(wiki_root).as_posix()
            summary = page.frontmatter.summary or page_summary(page.body)
            source_count = len(page.frontmatter.source_ids)
            lines.append(
                f"- [[{page.frontmatter.title}]] ({relative_path}) - {summary} "
                f"[sources: {source_count}]"
            )
        lines.append("")

    return "\n".join(lines)


def extract_wiki_links(text: str) -> list[str]:
    return [match.group(1).strip() for match in WIKI_LINK_PATTERN.finditer(text)]


def unique_relative_paths(wiki_root: Path, paths: list[Path]) -> list[str]:
    relative_paths: list[str] = []
    for path in paths:
        relative_path = path.relative_to(wiki_root).as_posix()
        if relative_path not in relative_paths:
            relative_paths.append(relative_path)
    return relative_paths


def append_log_entry(
    *,
    wiki_root: Path,
    operation: str,
    title: str,
    detail_lines: list[str],
    date_stamp: str | None = None,
) -> None:
    log_path = wiki_root / "log.md"
    existing = log_path.read_text(encoding="utf-8").rstrip()
    write_text(log_path, render_log_with_entry(existing=existing, operation=operation, title=title, detail_lines=detail_lines, date_stamp=date_stamp))


def render_log_with_entry(
    *,
    existing: str,
    operation: str,
    title: str,
    detail_lines: list[str],
    date_stamp: str | None = None,
) -> str:
    if date_stamp is None:
        date_stamp = datetime.now().astimezone().date().isoformat()

    lines = [
        existing,
        "",
        f"## [{date_stamp}] {operation} | {title}",
        "",
    ]
    lines.extend(detail_lines)
    return "\n".join(lines)


def write_analysis_page(
    *,
    wiki_root: Path,
    title: str,
    body: str,
    source_ids: list[str],
    timestamp: str,
    summary: str | None = None,
    aliases: list[str] | None = None,
    tags: list[str] | None = None,
    related_topics: list[str] | None = None,
) -> Path:
    target = wiki_root / "analyses" / f"{slugify(title)}.md"
    write_text(
        target,
        render_analysis_page(
            title=title,
            body=body,
            source_ids=source_ids,
            timestamp=timestamp,
            summary=summary,
            aliases=aliases,
            tags=tags,
            related_topics=related_topics,
        ),
    )
    return target


def render_analysis_page(
    *,
    title: str,
    body: str,
    source_ids: list[str],
    timestamp: str,
    summary: str | None = None,
    aliases: list[str] | None = None,
    tags: list[str] | None = None,
    related_topics: list[str] | None = None,
) -> str:
    frontmatter = PageFrontmatter(
        title=title,
        type="analysis",
        updated_at=timestamp,
        source_ids=source_ids,
        summary=summary,
        aliases=aliases or [],
        tags=tags or [],
        related_topics=related_topics or [],
        confidence=0.6,
        last_reviewed_at=timestamp,
    )
    return render_page(frontmatter, body)
