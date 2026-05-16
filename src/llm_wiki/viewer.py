from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import markdown as md
from fasthtml.common import A, Article, Button, Div, Form, H1, H2, Header, Input, Li, Main, Nav, NotStr, P, Script, Section, Small, Span, Style, Titled, Ul, fast_app

from .config import DEFAULT_VAULT_DIRNAME, resolve_state_root, resolve_wiki_root
from .filesystem import slugify
from .models import WikiPage
from .retrieval import retrieve_pages
from .review import preview_change_plan
from .reviews import REVIEW_STATES, list_reviews, load_review, review_to_change_plan
from .wiki import collect_wiki_pages, extract_wiki_links, page_summary

INLINE_MATH_PATTERN = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$")
BLOCK_MATH_PATTERN = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
LOG_ENTRY_PATTERN = re.compile(r"^## \[(?P<date>[^\]]+)\] (?P<kind>[^|]+)\| (?P<title>.+)$", re.MULTILINE)

VIEWER_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Spectral:wght@500;600;700&display=swap');

:root {
  --bg: #f6f1e8;
  --panel: rgba(255, 252, 246, 0.88);
  --panel-strong: #fffaf2;
  --text: #1e2a24;
  --muted: #5f6b61;
  --line: rgba(30, 42, 36, 0.12);
  --accent: #9c4b2c;
  --accent-soft: rgba(156, 75, 44, 0.1);
  --forest: #234235;
  --shadow: 0 24px 60px rgba(24, 30, 26, 0.12);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: radial-gradient(circle at top, #fff8ef 0%, var(--bg) 45%, #efe7db 100%); color: var(--text); }
body { font-family: 'IBM Plex Sans', sans-serif; line-height: 1.6; }
a { color: var(--forest); text-decoration-thickness: 1px; text-underline-offset: 2px; }
main.viewer-shell { max-width: 1440px; margin: 0 auto; padding: 32px 24px 56px; display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 28px; }
.viewer-sidebar, .viewer-panel { background: var(--panel); backdrop-filter: blur(10px); border: 1px solid var(--line); border-radius: 24px; box-shadow: var(--shadow); }
.viewer-sidebar { padding: 24px; position: sticky; top: 20px; height: fit-content; }
.viewer-panel { padding: 32px; }
.brand { display: grid; gap: 8px; margin-bottom: 18px; }
.brand h1 { margin: 0; font: 700 2rem/1 'Spectral', serif; letter-spacing: -0.02em; }
.brand p { margin: 0; color: var(--muted); font-size: 0.95rem; }
.search-form { display: grid; gap: 10px; margin: 22px 0 28px; }
.search-form input { width: 100%; border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; background: #fffdf9; color: var(--text); font: inherit; }
.sidebar-section { margin-top: 24px; }
.sidebar-section h2 { margin: 0 0 10px; font: 600 0.9rem/1.2 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
.sidebar-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.sidebar-list li a { display: block; padding: 8px 10px; border-radius: 12px; text-decoration: none; }
.sidebar-list li a:hover { background: rgba(35, 66, 53, 0.08); }
.hero { display: grid; gap: 10px; margin-bottom: 28px; }
.hero h1 { margin: 0; font: 700 3rem/1.02 'Spectral', serif; letter-spacing: -0.03em; }
.hero p { margin: 0; color: var(--muted); max-width: 70ch; }
.chip-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.chip { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 12px; background: var(--accent-soft); color: var(--accent); font: 500 0.86rem/1 'IBM Plex Mono', monospace; }
.page-grid { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 24px; align-items: start; }
.page-meta { display: grid; gap: 18px; }
.meta-card, .result-card, .log-card { border: 1px solid var(--line); border-radius: 18px; background: var(--panel-strong); padding: 18px; }
.meta-card h2, .result-card h2, .log-card h2 { margin: 0 0 12px; font: 600 1rem/1.1 'IBM Plex Mono', monospace; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
.meta-list, .log-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.meta-list li, .log-list li { color: var(--muted); }
.page-content { font-size: 1.03rem; }
.page-content h1, .page-content h2, .page-content h3 { font-family: 'Spectral', serif; line-height: 1.1; letter-spacing: -0.02em; }
.page-content h1 { font-size: 2.6rem; margin-top: 0; }
.page-content h2 { font-size: 1.8rem; margin-top: 2rem; }
.page-content h3 { font-size: 1.35rem; margin-top: 1.6rem; }
.page-content p, .page-content li { max-width: 70ch; }
.page-content code { font-family: 'IBM Plex Mono', monospace; background: rgba(30, 42, 36, 0.06); border-radius: 6px; padding: 0.1rem 0.35rem; }
.page-content pre { overflow-x: auto; background: #1b241f; color: #f6f1e8; border-radius: 16px; padding: 16px; }
.math-inline, .math-block { overflow-x: auto; }
.math-block { margin: 1.2rem 0; padding: 0.8rem 1rem; background: rgba(35, 66, 53, 0.04); border-left: 3px solid rgba(35, 66, 53, 0.2); border-radius: 12px; }
.result-list { display: grid; gap: 16px; }
.result-card h3 { margin: 0 0 8px; font: 600 1.3rem/1.15 'Spectral', serif; }
.result-meta { color: var(--muted); font-size: 0.92rem; }
.section-title { margin: 32px 0 14px; font: 600 1rem/1 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
@media (max-width: 1100px) {
  main.viewer-shell { grid-template-columns: 1fr; }
  .viewer-sidebar { position: static; }
  .page-grid { grid-template-columns: 1fr; }
}
"""

MATHJAX_CONFIG = """
window.MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
    displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']],
    processEscapes: true
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
  }
};
"""


@dataclass
class ViewerPage:
    page: WikiPage
    slug: str


def create_viewer_app(*, base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME):
    wiki_root = resolve_wiki_root(base_path, vault_name)
    state_root = resolve_state_root(base_path, vault_name)
    hdrs = (
        Style(VIEWER_STYLE),
        Script(MATHJAX_CONFIG),
        Script(src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js", id="MathJax-script", **{"async": True}),
    )
    app, rt = fast_app(hdrs=hdrs, title="LLM Wiki Viewer", surreal=False)

    @rt("/")
    def home(q: str = ""):
        pages = load_viewer_pages(wiki_root)
        content = render_home_content(wiki_root=wiki_root, pages=pages, query=q)
        return viewer_shell(content=content, pages=pages, query=q)

    @rt("/page/{slug}")
    def page(slug: str):
        pages = load_viewer_pages(wiki_root)
        page_map = {item.slug: item for item in pages}
        viewer_page = page_map.get(slug)
        if viewer_page is None:
            content = render_not_found(slug)
            return viewer_shell(content=content, pages=pages)
        content = render_page_content(wiki_root=wiki_root, pages=pages, current=viewer_page)
        return viewer_shell(content=content, pages=pages)

    @rt("/log")
    def log():
        pages = load_viewer_pages(wiki_root)
        content = render_log_content(wiki_root)
        return viewer_shell(content=content, pages=pages)

    @rt("/issues")
    def issues():
        pages = load_viewer_pages(wiki_root)
        content = render_issue_content(state_root)
        return viewer_shell(content=content, pages=pages)

    @rt("/operations")
    def operations():
        pages = load_viewer_pages(wiki_root)
        content = render_operations_content(state_root)
        return viewer_shell(content=content, pages=pages)

    @rt("/reviews")
    def reviews():
        pages = load_viewer_pages(wiki_root)
        content = render_reviews_content(state_root)
        return viewer_shell(content=content, pages=pages)

    @rt("/reviews/{review_id}")
    def review_detail(review_id: str):
        pages = load_viewer_pages(wiki_root)
        content = render_review_detail_content(state_root=state_root, repo_root=base_path, review_id=review_id)
        return viewer_shell(content=content, pages=pages)

    return app


def load_viewer_pages(wiki_root: Path) -> list[ViewerPage]:
    pages = collect_wiki_pages(wiki_root)
    return [ViewerPage(page=page, slug=slugify(page.frontmatter.title)) for page in pages]


def viewer_shell(*, content, pages: list[ViewerPage], query: str = ""):
    return Titled(
        "LLM Wiki Viewer",
        Main(
            render_sidebar(pages=pages, query=query),
            content,
            cls="viewer-shell",
        ),
    )


def render_sidebar(*, pages: list[ViewerPage], query: str):
    grouped = group_pages(pages)
    recent = pages[-8:]
    return Nav(
        Div(
            Div(
                H1("LLM Wiki"),
                P("A local viewer for the persistent markdown wiki, with math-aware rendering and graph-friendly navigation."),
                cls="brand",
            ),
            search_form(query),
            sidebar_section("Recent Pages", recent),
            sidebar_section("Concepts", grouped["concept"]),
            sidebar_section("Entities", grouped["entity"]),
            sidebar_section("Sources", grouped["source"]),
            sidebar_section("Analyses", grouped["analysis"]),
            sidebar_section("Overviews", grouped["overview"]),
            cls="viewer-sidebar",
        )
    )


def search_form(query: str):
    return Div(
        A("Home", href="/"),
        " ",
        A("Recent Log", href="/log"),
        " ",
        A("Issues", href="/issues"),
        " ",
        A("Operations", href="/operations"),
        " ",
        A("Reviews", href="/reviews"),
        Form(
            Input(type="search", name="q", value=query, placeholder="Search wiki pages, aliases, headings, maths topics...", autofocus=True),
            Button("Search", type="submit"),
            method="get",
            cls="search-form",
        ),
    )


def sidebar_section(title: str, pages: list[ViewerPage]):
    if not pages:
        return Div(cls="sidebar-section")
    return Section(
        H2(title),
        Ul(*[Li(A(item.page.frontmatter.title, href=f"/page/{item.slug}")) for item in pages], cls="sidebar-list"),
        cls="sidebar-section",
    )


def render_home_content(*, wiki_root: Path, pages: list[ViewerPage], query: str):
    if query.strip():
        matches = retrieve_pages(query, [item.page for item in pages], limit=12)
        return Div(
            Header(
                H1("Search Results", cls="hero-title"),
                P(f"Results for “{query}” ranked using title, alias, heading, summary, tag, and body signals.", cls="hero-subtitle"),
                cls="hero",
            ),
            Div(*[render_result_card(match) for match in matches], cls="result-list") if matches else P("No wiki pages matched this query yet."),
            cls="viewer-panel",
        )

    recent_entries = read_log_entries(wiki_root)[:8]
    featured = pages[:8]
    return Div(
        Header(
            H1("Persistent Knowledge, Browseable", cls="hero-title"),
            P(
                "The wiki stays the source of truth. This viewer adds search, backlinks, recent activity, and math-capable markdown rendering without replacing the markdown files on disk.",
                cls="hero-subtitle",
            ),
            Div(
                Span(f"{len(pages)} pages indexed", cls="chip"),
                Span(f"{len(group_pages(pages)['source'])} source summaries", cls="chip"),
                Span("MathJax enabled", cls="chip"),
                cls="chip-row",
            ),
            cls="hero",
        ),
        H2("Featured Pages", cls="section-title"),
        Div(*[render_feature_card(item) for item in featured], cls="result-list"),
        H2("Recent Activity", cls="section-title"),
        Div(*[render_log_card(entry) for entry in recent_entries], cls="result-list") if recent_entries else P("No recent log activity yet."),
        cls="viewer-panel",
    )


def render_page_content(*, wiki_root: Path, pages: list[ViewerPage], current: ViewerPage):
    backlinks = compute_backlinks(pages, current.page.frontmatter.title)
    rendered_html = render_markdown_with_math(current.page.body, title_index={item.page.frontmatter.title: item.slug for item in pages})
    return Div(
        Header(
            H1(current.page.frontmatter.title),
            P(current.page.frontmatter.summary or page_summary(current.page.body)),
            Div(
                Span(current.page.frontmatter.type, cls="chip"),
                Span(f"{len(current.page.frontmatter.source_ids)} source ids", cls="chip"),
                *(Span(tag, cls="chip") for tag in current.page.frontmatter.tags[:4]),
                cls="chip-row",
            ),
            cls="hero",
        ),
        Div(
            Article(NotStr(rendered_html), cls="page-content"),
            Div(
                render_meta_card(current),
                render_backlinks_card(backlinks),
                cls="page-meta",
            ),
            cls="page-grid",
        ),
        cls="viewer-panel",
    )


def render_not_found(slug: str):
    return Div(
        Header(
            H1("Page Not Found"),
            P(f"No page with slug `{slug}` exists in the current wiki."),
            cls="hero",
        ),
        cls="viewer-panel",
    )


def render_log_content(wiki_root: Path):
    entries = read_log_entries(wiki_root)
    return Div(
        Header(
            H1("Recent Log Activity"),
            P("Chronological changes across ingest, query filing, and lint passes."),
            cls="hero",
        ),
        Div(*[render_log_card(entry) for entry in entries], cls="result-list") if entries else P("No log entries yet."),
        cls="viewer-panel",
    )


def render_issue_content(state_root: Path):
    issues = read_issue_entries(state_root)
    grouped = group_issue_entries(issues)
    return Div(
        Header(
            H1("Maintenance Issues"),
            P("Structured lint findings persisted under `vault/state/issues/` for review and follow-up."),
            cls="hero",
        ),
        H2("Errors", cls="section-title"),
        Div(*[render_issue_card(issue) for issue in grouped["error"]], cls="result-list") if grouped["error"] else P("No error issues."),
        H2("Warnings", cls="section-title"),
        Div(*[render_issue_card(issue) for issue in grouped["warning"]], cls="result-list") if grouped["warning"] else P("No warning issues."),
        H2("Suggestions", cls="section-title"),
        Div(*[render_issue_card(issue) for issue in grouped["suggestion"]], cls="result-list") if grouped["suggestion"] else P("No suggestion issues."),
        H2("LLM Review", cls="section-title"),
        Div(*[render_issue_card(issue) for issue in grouped["llm"]], cls="result-list") if grouped["llm"] else P("No LLM review issues."),
        cls="viewer-panel",
    )


def render_operations_content(state_root: Path):
    operations = read_operation_entries(state_root)
    return Div(
        Header(
            H1("Operation Artifacts"),
            P("Recent ingest, query, and lint metadata persisted under `vault/state/operations/`."),
            cls="hero",
        ),
        Div(*[render_operation_card(entry) for entry in operations], cls="result-list") if operations else P("No operation artifacts yet."),
        cls="viewer-panel",
    )


def render_reviews_content(state_root: Path):
    grouped = read_review_entries(state_root)
    return Div(
        Header(
            H1("Review Queue"),
            P("Saved change plans persisted under `vault/state/reviews/` for inspection before apply or rejection."),
            cls="hero",
        ),
        H2("Pending", cls="section-title"),
        Div(*[render_review_card(review) for review in grouped["pending"]], cls="result-list") if grouped["pending"] else P("No pending reviews."),
        H2("Applied", cls="section-title"),
        Div(*[render_review_card(review) for review in grouped["applied"]], cls="result-list") if grouped["applied"] else P("No applied reviews."),
        H2("Rejected", cls="section-title"),
        Div(*[render_review_card(review) for review in grouped["rejected"]], cls="result-list") if grouped["rejected"] else P("No rejected reviews."),
        cls="viewer-panel",
    )


def render_review_detail_content(*, state_root: Path, repo_root: Path, review_id: str):
    try:
        review = load_review(state_root=state_root, review_id=review_id)
    except FileNotFoundError:
        return Div(
            Header(
                H1("Review Not Found"),
                P(f"No review with ID `{review_id}` exists in the review queue."),
                cls="hero",
            ),
            cls="viewer-panel",
        )

    plan = review_to_change_plan(review, repo_root=repo_root)
    preview = preview_change_plan(plan, repo_root=repo_root)
    rendered_preview = md.markdown(
        preview,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html5",
    )
    return Div(
        Header(
            H1(review.payload.title),
            P(f"{review.payload.operation} • {review.payload.status} • {review.payload.created_at}"),
            Div(
                Span(f"{len(review.payload.changes)} file changes", cls="chip"),
                Span(review.payload.review_id, cls="chip"),
                cls="chip-row",
            ),
            cls="hero",
        ),
        Article(NotStr(rendered_preview), cls="page-content"),
        cls="viewer-panel",
    )


def render_feature_card(item: ViewerPage):
    summary = item.page.frontmatter.summary or page_summary(item.page.body)
    return Section(
        H2(A(item.page.frontmatter.title, href=f"/page/{item.slug}")),
        P(summary),
        Small(f"{item.page.frontmatter.type} • {len(item.page.frontmatter.source_ids)} source ids"),
        cls="result-card",
    )


def render_result_card(match):
    return Section(
        H2(A(match.page.frontmatter.title, href=f"/page/{slugify(match.page.frontmatter.title)}")),
        P(match.snippet),
        P(f"Score: {match.score:.1f} • Reasons: {', '.join(match.reasons)}", cls="result-meta"),
        cls="result-card",
    )


def render_log_card(entry: dict[str, str]):
    return Section(
        H2(entry["title"]),
        P(f"{entry['date']} • {entry['kind'].strip()}"),
        cls="log-card",
    )


def render_issue_card(issue: dict[str, object]):
    related = ", ".join(str(item) for item in issue.get("related_pages", [])) or "none"
    suggestion = issue.get("suggestion") or "No suggested action recorded."
    return Section(
        H2(str(issue["title"])),
        P(str(issue["detail"])),
        P(f"Category: {issue['category']} • Confidence: {float(issue['confidence']):.2f}", cls="result-meta"),
        P(f"Related pages: {related}", cls="result-meta"),
        P(str(suggestion), cls="result-meta"),
        cls="result-card",
    )


def render_operation_card(entry: dict[str, object]):
    metadata = entry.get("metadata", {})
    details = entry.get("details", {})
    operation = metadata.get("operation", "unknown")
    timestamp = metadata.get("timestamp", "unknown")
    model = metadata.get("llm_model") or metadata.get("llm_provider") or "no-llm"
    return Section(
        H2(f"{operation} • {timestamp}"),
        P(f"Model: {model}"),
        P(f"Schema: {metadata.get('schema_domain', 'unknown')} • Raw fallback: {metadata.get('raw_source_fallback', False)}", cls="result-meta"),
        P(json.dumps(details, sort_keys=True)[:320], cls="result-meta"),
        cls="result-card",
    )


def render_review_card(entry: dict[str, object]):
    return Section(
        H2(A(str(entry["title"]), href=f"/reviews/{entry['review_id']}")),
        P(f"{entry['operation']} • {entry['status']} • {entry['created_at']}"),
        P(f"Files changed: {len(entry.get('changes', []))}", cls="result-meta"),
        P(str(entry["review_id"]), cls="result-meta"),
        cls="result-card",
    )


def render_meta_card(current: ViewerPage):
    fm = current.page.frontmatter
    return Section(
        H2("Metadata"),
        Ul(
            Li(f"Type: {fm.type}"),
            Li(f"Updated: {fm.updated_at}"),
            Li(f"Summary: {fm.summary or page_summary(current.page.body)}"),
            Li(f"Aliases: {', '.join(fm.aliases) or 'none'}"),
            Li(f"Related topics: {', '.join(fm.related_topics) or 'none'}"),
            Li(f"Source IDs: {', '.join(fm.source_ids) or 'none'}"),
            cls="meta-list",
        ),
        cls="meta-card",
    )


def render_backlinks_card(backlinks: list[ViewerPage]):
    return Section(
        H2("Backlinks"),
        Ul(
            *[Li(A(item.page.frontmatter.title, href=f"/page/{item.slug}")) for item in backlinks],
            cls="meta-list",
        ) if backlinks else P("No backlinks yet."),
        cls="meta-card",
    )


def group_pages(pages: list[ViewerPage]) -> dict[str, list[ViewerPage]]:
    grouped: dict[str, list[ViewerPage]] = {
        "overview": [],
        "entity": [],
        "concept": [],
        "source": [],
        "analysis": [],
    }
    for item in sorted(pages, key=lambda page: page.page.frontmatter.title.lower()):
        grouped[item.page.frontmatter.type].append(item)
    return grouped


def compute_backlinks(pages: list[ViewerPage], title: str) -> list[ViewerPage]:
    backlinks = [item for item in pages if title in extract_wiki_links(item.page.body)]
    backlinks.sort(key=lambda item: item.page.frontmatter.title.lower())
    return backlinks


def read_log_entries(wiki_root: Path) -> list[dict[str, str]]:
    log_path = wiki_root / "log.md"
    if not log_path.exists():
        return []
    entries = [
        {"date": match.group("date"), "kind": match.group("kind"), "title": match.group("title").strip()}
        for match in LOG_ENTRY_PATTERN.finditer(log_path.read_text(encoding="utf-8"))
    ]
    entries.reverse()
    return entries


def read_issue_entries(state_root: Path) -> list[dict[str, object]]:
    issue_path = state_root / "issues/lint-issues.json"
    if not issue_path.exists():
        return []
    payload = json.loads(issue_path.read_text(encoding="utf-8"))
    issues = payload.get("issues", [])
    if not isinstance(issues, list):
        return []
    return issues


def group_issue_entries(issues: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {"error": [], "warning": [], "suggestion": [], "llm": []}
    for issue in issues:
        severity = str(issue.get("severity", "suggestion"))
        if severity == "llm":
            grouped["llm"].append(issue)
        elif severity in grouped:
            grouped[severity].append(issue)
    return grouped


def read_operation_entries(state_root: Path) -> list[dict[str, object]]:
    operations_root = state_root / "operations"
    if not operations_root.exists():
        return []
    entries = []
    for path in sorted(operations_root.glob("*.json"), reverse=True)[:12]:
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    return entries


def read_review_entries(state_root: Path) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {status: [] for status in REVIEW_STATES}
    for status in REVIEW_STATES:
        grouped[status] = [
            review.payload.model_dump()
            for review in list_reviews(state_root=state_root, status=status)
        ]
    return grouped


def render_markdown_with_math(text: str, *, title_index: dict[str, str]) -> str:
    placeholder_map: dict[str, str] = {}

    def replace_block(match: re.Match[str]) -> str:
        key = f"@@BLOCKMATH{len(placeholder_map)}@@"
        latex = match.group(1).strip()
        placeholder_map[key] = f'<div class="math-block">\\[{html.escape(latex)}\\]</div>'
        return key

    def replace_inline(match: re.Match[str]) -> str:
        key = f"@@INLINEMATH{len(placeholder_map)}@@"
        latex = match.group(1).strip()
        placeholder_map[key] = f'<span class="math-inline">\\({html.escape(latex)}\\)</span>'
        return key

    with_math_placeholders = BLOCK_MATH_PATTERN.sub(replace_block, text)
    with_math_placeholders = INLINE_MATH_PATTERN.sub(replace_inline, with_math_placeholders)
    wiki_link_markdown = WIKI_LINK_PATTERN.sub(
        lambda match: f"[{match.group(1)}](/page/{quote(title_index.get(match.group(1), slugify(match.group(1))))})",
        with_math_placeholders,
    )
    html_output = md.markdown(
        wiki_link_markdown,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html5",
    )
    for placeholder, replacement in placeholder_map.items():
        html_output = html_output.replace(placeholder, replacement)
    return html_output
