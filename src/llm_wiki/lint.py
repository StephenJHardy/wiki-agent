from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .config import DEFAULT_VAULT_DIRNAME, resolve_state_root, resolve_wiki_root
from .filesystem import read_json, render_json
from .llm import get_llm_provider
from .llm.base import LLMError
from .llm.config import load_llm_settings
from .llm.prompts import build_lint_prompt, build_system_instruction, load_prompt_context
from .llm.schemas import StructuredLintReview
from .models import SourceRegistry
from .planning import ChangePlan, FileChange, OperationArtifact, OperationMetadata, apply_change_plan, save_operation_artifact
from .wiki import collect_wiki_pages, extract_wiki_links, render_analysis_page, render_index, render_log_with_entry


class LintIssue(BaseModel):
    issue_id: str
    category: str
    severity: str
    confidence: float
    title: str
    detail: str
    related_pages: list[str] = Field(default_factory=list)
    suggestion: str | None = None


class LintIssueState(BaseModel):
    updated_at: str
    issues: list[LintIssue] = Field(default_factory=list)


class LintResult:
    def __init__(
        self,
        report_markdown: str,
        issues: list[LintIssue],
        written_page: Path | None,
        change_plan: ChangePlan,
        artifact_path: Path,
        dry_run: bool,
    ) -> None:
        self.report_markdown = report_markdown
        self.issues = issues
        self.written_page = written_page
        self.change_plan = change_plan
        self.artifact_path = artifact_path
        self.dry_run = dry_run

    @property
    def errors(self) -> list[str]:
        return [issue.detail for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[str]:
        return [issue.detail for issue in self.issues if issue.severity == "warning"]

    @property
    def suggestions(self) -> list[str]:
        return [issue.detail for issue in self.issues if issue.severity == "suggestion"]

    @property
    def llm_findings(self) -> list[str]:
        return [issue.detail for issue in self.issues if issue.category.startswith("llm_")]


def run_lint(
    *,
    base_path: Path,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    file_report: bool = False,
    title: str | None = None,
    use_llm: bool = True,
    provider_name: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
    max_file_changes: int | None = None,
) -> LintResult:
    wiki_root = resolve_wiki_root(base_path, vault_name)
    state_root = resolve_state_root(base_path, vault_name)
    llm_settings = load_llm_settings(base_path=base_path, provider=provider_name, model=model)
    _, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)

    pages = collect_wiki_pages(wiki_root)
    registry = SourceRegistry.model_validate(read_json(state_root / "sources.json"))

    title_to_page = {page.frontmatter.title: page for page in pages}
    path_by_title = {page.frontmatter.title: Path(page.path) for page in pages}
    outbound_links: dict[str, list[str]] = {}
    inbound_counts: defaultdict[str, int] = defaultdict(int)

    for page in pages:
        links = extract_wiki_links(page.body)
        outbound_links[page.frontmatter.title] = links
        for link in links:
            inbound_counts[link] += 1

    issues = []
    issues.extend(broken_link_issues(pages, title_to_page))
    issues.extend(missing_frontmatter_source_issues(pages))
    issues.extend(index_coverage_issues(wiki_root, title_to_page))
    issues.extend(stale_page_issues(pages, registry))
    issues.extend(orphan_page_issues(pages, inbound_counts))
    issues.extend(unlinked_cluster_issues(pages, outbound_links, inbound_counts))
    issues.extend(missing_cross_reference_issues(pages, outbound_links, path_by_title))
    issues.extend(missing_claim_timeline_issues(pages))

    llm_issues, llm_used = llm_review(
        base_path=base_path,
        pages=pages[:8],
        structural_findings=[issue.detail for issue in issues],
        vault_name=vault_name,
        use_llm=use_llm,
        provider_name=provider_name,
        model=model,
    )
    issues.extend(llm_issues)
    issues = dedupe_issues(issues)

    report_markdown = render_lint_report(issues)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = OperationMetadata(
        timestamp=timestamp,
        operation="lint",
        schema_domain=schema_bundle.config.domain,
        prompt_versions=schema_bundle.config.prompt_versions,
        llm_requested=use_llm,
        llm_used=llm_used,
        llm_provider=llm_settings.provider,
        llm_model=llm_settings.model if llm_settings.enabled else None,
    )

    issue_state = LintIssueState(updated_at=timestamp, issues=issues)
    issues_path = state_root / "issues/lint-issues.json"
    plan = ChangePlan(operation="lint", title=title or f"Wiki Lint {datetime.now().astimezone().date().isoformat()}", metadata=metadata)
    written_page: Path | None = None
    if file_report:
        page_title = title or f"Wiki Lint {datetime.now().astimezone().date().isoformat()}"
        written_page = wiki_root / "analyses" / f"{slugify_title(page_title)}.md"
        report_after = render_analysis_page(
            title=page_title,
            body=report_markdown,
            source_ids=[],
            timestamp=timestamp,
            summary="Persisted lint report for wiki maintenance.",
            tags=["analysis", "lint"],
            related_topics=[],
        )
        next_pages = [page for page in pages if Path(page.path) != written_page]
        next_pages.append(page_from_content(written_page, report_after))
        index_after = render_index(wiki_root=wiki_root, pages=next_pages)
        detail_lines = [
            f"- Issues: {len(issues)}",
            f"- Errors: {sum(1 for issue in issues if issue.severity == 'error')}",
            f"- Warnings: {sum(1 for issue in issues if issue.severity == 'warning')}",
            f"- Suggestions: {sum(1 for issue in issues if issue.severity == 'suggestion')}",
            f"- Filed report: `{written_page.relative_to(wiki_root).as_posix()}`",
        ]
        detail_lines.extend(operation_metadata_lines(metadata))
        log_after = render_log_with_entry(
            existing=(wiki_root / "log.md").read_text(encoding="utf-8").rstrip(),
            operation="lint",
            title=page_title,
            detail_lines=detail_lines,
        )
        plan = ChangePlan(
            operation="lint",
            title=page_title,
            metadata=metadata,
            detail_lines=detail_lines,
            changes=build_changes(
                [
                    (issues_path, render_json(issue_state.model_dump())),
                    (written_page, report_after),
                    (wiki_root / "index.md", index_after),
                    (wiki_root / "log.md", log_after),
                ]
            ),
        )
    else:
        plan = ChangePlan(
            operation="lint",
            title="Lint issue state",
            metadata=metadata,
            detail_lines=[f"- Issues: {len(issues)}", *operation_metadata_lines(metadata)],
            changes=build_changes([(issues_path, render_json(issue_state.model_dump()))]),
        )
    plan.validate(max_file_changes=max_file_changes)
    if not dry_run:
        apply_change_plan(plan)

    artifact_path = save_operation_artifact(
        state_root=state_root,
        artifact=OperationArtifact(
            metadata=metadata,
            details={
                "issue_count": len(issues),
                "categories": Counter(issue.category for issue in issues),
            },
            change_summary={
                "file_changes": len(plan.changed_files()),
                "file_report": file_report,
                "dry_run": dry_run,
            },
        ),
    )

    return LintResult(
        report_markdown=report_markdown,
        issues=issues,
        written_page=written_page,
        change_plan=plan,
        artifact_path=artifact_path,
        dry_run=dry_run,
    )


def propose_lint_fix_plans(
    *,
    base_path: Path,
    issues: list[LintIssue],
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    max_file_changes: int | None = None,
) -> list[ChangePlan]:
    wiki_root = resolve_wiki_root(base_path, vault_name)
    _, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = OperationMetadata(
        timestamp=timestamp,
        operation="lint-fix",
        schema_domain=schema_bundle.config.domain,
        prompt_versions=schema_bundle.config.prompt_versions,
    )

    pages = collect_wiki_pages(wiki_root)
    plans: list[ChangePlan] = []

    index_plan = propose_index_fix(wiki_root=wiki_root, pages=pages, issues=issues, metadata=metadata)
    if index_plan is not None:
        index_plan.validate(max_file_changes=max_file_changes)
        plans.append(index_plan)

    claim_timeline_plan = propose_claim_timeline_fix(wiki_root=wiki_root, pages=pages, issues=issues, metadata=metadata)
    if claim_timeline_plan is not None:
        claim_timeline_plan.validate(max_file_changes=max_file_changes)
        plans.append(claim_timeline_plan)

    link_fix_plan = propose_obvious_broken_link_fix(wiki_root=wiki_root, pages=pages, issues=issues, metadata=metadata)
    if link_fix_plan is not None:
        link_fix_plan.validate(max_file_changes=max_file_changes)
        plans.append(link_fix_plan)

    return plans


def propose_index_fix(
    *,
    wiki_root: Path,
    pages: list,
    issues: list[LintIssue],
    metadata: OperationMetadata,
) -> ChangePlan | None:
    index_issues = [issue for issue in issues if issue.category == "index_coverage"]
    if not index_issues:
        return None
    index_after = render_index(wiki_root=wiki_root, pages=pages)
    return ChangePlan(
        operation="lint-fix",
        title="Rebuild index coverage",
        metadata=metadata,
        detail_lines=[
            "- Fixes lint issue category: `index_coverage`",
            f"- Pages restored to index: {len(index_issues)}",
        ],
        changes=build_changes([(wiki_root / "index.md", index_after)]),
    )


def propose_claim_timeline_fix(
    *,
    wiki_root: Path,
    pages: list,
    issues: list[LintIssue],
    metadata: OperationMetadata,
) -> ChangePlan | None:
    issue_titles = {
        title
        for issue in issues
        if issue.category == "missing_claim_timeline"
        for title in issue.related_pages
    }
    if not issue_titles:
        return None

    changes: list[tuple[Path, str]] = []
    for page in pages:
        if page.frontmatter.title not in issue_titles:
            continue
        body_after = append_claim_timeline_placeholder(page.body)
        if body_after == page.body:
            continue
        changes.append((Path(page.path), render_page_from_existing(page, body_after)))

    if not changes:
        return None
    return ChangePlan(
        operation="lint-fix",
        title="Add missing claim timeline sections",
        metadata=metadata,
        detail_lines=[
            "- Fixes lint issue category: `missing_claim_timeline`",
            f"- Pages updated: {len(changes)}",
            "- Placeholder entries are intentionally conservative; run `refresh-source` to backfill source-specific entries.",
        ],
        changes=build_changes(changes),
    )


def propose_obvious_broken_link_fix(
    *,
    wiki_root: Path,
    pages: list,
    issues: list[LintIssue],
    metadata: OperationMetadata,
) -> ChangePlan | None:
    broken_issues = [issue for issue in issues if issue.category == "broken_link"]
    if not broken_issues:
        return None

    title_by_casefold = {page.frontmatter.title.casefold(): page.frontmatter.title for page in pages}
    pages_by_title = {page.frontmatter.title: page for page in pages}
    replacements_by_page: defaultdict[str, dict[str, str]] = defaultdict(dict)
    for issue in broken_issues:
        if len(issue.related_pages) != 1:
            continue
        broken_link = extract_broken_link_from_detail(issue.detail)
        if broken_link is None:
            continue
        corrected = title_by_casefold.get(broken_link.casefold())
        if corrected is None or corrected == broken_link:
            continue
        source_title = issue.related_pages[0]
        replacements_by_page[source_title][broken_link] = corrected

    changes: list[tuple[Path, str]] = []
    for title, replacements in sorted(replacements_by_page.items()):
        page = pages_by_title.get(title)
        if page is None:
            continue
        body_after = page.body
        for before, after in sorted(replacements.items()):
            body_after = body_after.replace(f"[[{before}]]", f"[[{after}]]")
        if body_after != page.body:
            changes.append((Path(page.path), render_page_from_existing(page, body_after)))

    if not changes:
        return None
    return ChangePlan(
        operation="lint-fix",
        title="Fix obvious broken wiki-link casing",
        metadata=metadata,
        detail_lines=[
            "- Fixes lint issue category: `broken_link`",
            "- Only exact case-insensitive title matches are rewritten.",
            f"- Pages updated: {len(changes)}",
        ],
        changes=build_changes(changes),
    )


def append_claim_timeline_placeholder(body: str) -> str:
    stripped = body.rstrip()
    if "## Claim Timeline" in stripped:
        return body
    return (
        stripped
        + "\n\n## Claim Timeline\n"
        + "- No claim timeline entries yet. Run `llm-wiki refresh-source` to backfill source-specific provenance.\n"
    )


def render_page_from_existing(page, body: str) -> str:
    from .markdown import render_page

    return render_page(page.frontmatter, body)


def extract_broken_link_from_detail(detail: str) -> str | None:
    links = extract_wiki_links(detail)
    if len(links) < 2:
        return None
    return links[-1]


def broken_link_issues(pages: list, title_to_page: dict[str, object]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for page in pages:
        for link in extract_wiki_links(page.body):
            if link not in title_to_page:
                issues.append(
                    lint_issue(
                        category="broken_link",
                        severity="error",
                        confidence=0.99,
                        title=f"Broken link from {page.frontmatter.title}",
                        detail=f"Broken link in [[{page.frontmatter.title}]] -> [[{link}]]",
                        related_pages=[page.frontmatter.title],
                        suggestion=f"Create [[{link}]] or remove the broken link from [[{page.frontmatter.title}]].",
                    )
                )
    return issues


def missing_frontmatter_source_issues(pages: list) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for page in pages:
        if page.frontmatter.type == "analysis":
            continue
        if not page.frontmatter.source_ids:
            issues.append(
                lint_issue(
                    category="missing_source_ids",
                    severity="warning",
                    confidence=0.95,
                    title=f"Missing source_ids on {page.frontmatter.title}",
                    detail=f"[[{page.frontmatter.title}]] has no `source_ids` in frontmatter.",
                    related_pages=[page.frontmatter.title],
                    suggestion=f"Add source provenance to [[{page.frontmatter.title}]].",
                )
            )
    return issues


def index_coverage_issues(wiki_root: Path, title_to_page: dict[str, object]) -> list[LintIssue]:
    index_text = (wiki_root / "index.md").read_text(encoding="utf-8")
    indexed_titles = set(extract_wiki_links(index_text))
    issues: list[LintIssue] = []
    for title in sorted(title_to_page):
        if title not in indexed_titles:
            issues.append(
                lint_issue(
                    category="index_coverage",
                    severity="warning",
                    confidence=0.95,
                    title=f"Page missing from index: {title}",
                    detail=f"[[{title}]] exists in the wiki but is missing from `index.md`.",
                    related_pages=[title],
                    suggestion=f"Rebuild or update `index.md` to include [[{title}]].",
                )
            )
    return issues


def stale_page_issues(pages: list, registry: SourceRegistry) -> list[LintIssue]:
    source_updates = {record.source_id: record.updated_at for record in registry.sources}
    issues: list[LintIssue] = []
    for page in pages:
        if not page.frontmatter.source_ids:
            continue
        newest_source_update = max(
            (source_updates.get(source_id, page.frontmatter.updated_at) for source_id in page.frontmatter.source_ids),
            default=page.frontmatter.updated_at,
        )
        if page.frontmatter.updated_at < newest_source_update:
            issues.append(
                lint_issue(
                    category="stale_page",
                    severity="warning",
                    confidence=0.8,
                    title=f"Potentially stale page: {page.frontmatter.title}",
                    detail=f"[[{page.frontmatter.title}]] may be stale relative to newer source updates.",
                    related_pages=[page.frontmatter.title],
                    suggestion=f"Review [[{page.frontmatter.title}]] against its newest source pages.",
                )
            )
    return issues


def orphan_page_issues(pages: list, inbound_counts: dict[str, int]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for page in pages:
        if page.frontmatter.type == "source":
            continue
        if inbound_counts.get(page.frontmatter.title, 0) == 0:
            issues.append(
                lint_issue(
                    category="orphan_page",
                    severity="suggestion",
                    confidence=0.8,
                    title=f"Orphan page: {page.frontmatter.title}",
                    detail=f"[[{page.frontmatter.title}]] has no inbound links and may be orphaned.",
                    related_pages=[page.frontmatter.title],
                    suggestion=f"Add inbound links to [[{page.frontmatter.title}]] from related concept, entity, or overview pages.",
                )
            )
    return issues


def unlinked_cluster_issues(pages: list, outbound_links: dict[str, list[str]], inbound_counts: dict[str, int]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for page in pages:
        if page.frontmatter.type == "source":
            continue
        outbound = outbound_links.get(page.frontmatter.title, [])
        inbound = inbound_counts.get(page.frontmatter.title, 0)
        if not outbound and inbound == 0:
            issues.append(
                lint_issue(
                    category="isolated_page",
                    severity="suggestion",
                    confidence=0.85,
                    title=f"Isolated page: {page.frontmatter.title}",
                    detail=f"[[{page.frontmatter.title}]] is isolated with no inbound or outbound links.",
                    related_pages=[page.frontmatter.title],
                    suggestion=f"Link [[{page.frontmatter.title}]] to nearby concept or entity pages.",
                )
            )
    return issues


def missing_cross_reference_issues(
    pages: list,
    outbound_links: dict[str, list[str]],
    path_by_title: dict[str, Path],
) -> list[LintIssue]:
    token_index: defaultdict[str, list[str]] = defaultdict(list)
    for page in pages:
        for token in page.frontmatter.title.lower().split():
            if len(token) >= 5:
                token_index[token].append(page.frontmatter.title)

    issues: list[LintIssue] = []
    for token, titles in token_index.items():
        unique_titles = sorted(set(titles))
        if len(unique_titles) < 2:
            continue
        for title in unique_titles:
            related = [other for other in unique_titles if other != title]
            if not any(other in outbound_links.get(title, []) for other in related):
                issues.append(
                    lint_issue(
                        category="missing_cross_reference",
                        severity="suggestion",
                        confidence=0.6,
                        title=f"Missing cross-links for {title}",
                        detail=f"[[{title}]] may need cross-links to related pages sharing `{token}`: " + ", ".join(f"[[{other}]]" for other in related[:3]),
                        related_pages=[title, *related[:3]],
                        suggestion=f"Consider linking [[{title}]] to {', '.join(f'[[{other}]]' for other in related[:3])}.",
                    )
                )
    return issues


def missing_claim_timeline_issues(pages: list) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for page in pages:
        if page.frontmatter.type not in {"entity", "concept"}:
            continue
        if "## Claim Timeline" in page.body:
            continue
        issues.append(
            lint_issue(
                category="missing_claim_timeline",
                severity="suggestion",
                confidence=0.9,
                title=f"Missing claim timeline: {page.frontmatter.title}",
                detail=f"[[{page.frontmatter.title}]] has no `Claim Timeline` section.",
                related_pages=[page.frontmatter.title],
                suggestion=f"Add a `Claim Timeline` section to [[{page.frontmatter.title}]] or refresh its source pages.",
            )
        )
    return issues


def render_lint_report(issues: list[LintIssue]) -> str:
    lines = ["# Wiki Lint Report", ""]
    for section_title, severities in (
        ("Errors", {"error"}),
        ("Warnings", {"warning"}),
        ("Suggestions", {"suggestion"}),
        ("LLM Review", {"llm"}),
    ):
        lines.extend(render_issue_section(section_title, issues, severities))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_issue_section(title: str, issues: list[LintIssue], severities: set[str]) -> list[str]:
    lines = [f"## {title}"]
    filtered = [issue for issue in issues if issue.severity in severities or issue.category.startswith("llm_")]
    if title != "LLM Review":
        filtered = [issue for issue in filtered if not issue.category.startswith("llm_")]
    else:
        filtered = [issue for issue in issues if issue.category.startswith("llm_")]
    if not filtered:
        lines.append("- None.")
        return lines
    filtered.sort(key=lambda issue: (issue.category, issue.title))
    for issue in filtered:
        detail = f"{issue.detail} (confidence: {issue.confidence:.2f})"
        if issue.suggestion:
            detail += f" Suggested action: {issue.suggestion}"
        lines.append(f"- {detail}")
    return lines


def llm_review(
    *,
    base_path: Path,
    pages: list,
    structural_findings: list[str],
    vault_name: str,
    use_llm: bool,
    provider_name: str | None,
    model: str | None,
) -> tuple[list[LintIssue], bool]:
    if not use_llm:
        return [], False
    provider = get_llm_provider(base_path=base_path, provider_name=provider_name, model=model)
    if provider is None:
        return [], False

    agent_guide, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)
    prompt = build_lint_prompt(pages=pages, structural_findings=structural_findings[:25], schema_bundle=schema_bundle)
    system_instruction = build_system_instruction(agent_guide, schema_bundle)
    try:
        structured = provider.generate_structured(
            prompt=prompt,
            schema=StructuredLintReview,
            system_instruction=system_instruction,
            temperature=0.1,
        )
    except LLMError:
        return [], False

    issues: list[LintIssue] = []
    issues.extend([llm_issue("llm_contradiction", "Possible contradiction", item) for item in structured.contradictions])
    issues.extend([llm_issue("llm_stale_claim", "Potentially stale", item) for item in structured.stale_claims])
    issues.extend([llm_issue("llm_missing_page", "Missing page", item) for item in structured.missing_pages])
    issues.extend([llm_issue("llm_missing_cross_reference", "Missing cross-reference", item) for item in structured.missing_cross_references])
    issues.extend([llm_issue("llm_research_gap", "Research gap", item) for item in structured.research_gaps])
    return issues, True


def lint_issue(
    *,
    category: str,
    severity: str,
    confidence: float,
    title: str,
    detail: str,
    related_pages: list[str],
    suggestion: str | None = None,
) -> LintIssue:
    return LintIssue(
        issue_id=slugify_title(f"{category}-{detail}"),
        category=category,
        severity=severity,
        confidence=confidence,
        title=title,
        detail=detail,
        related_pages=related_pages,
        suggestion=suggestion,
    )


def llm_issue(category: str, title: str, detail: str) -> LintIssue:
    return lint_issue(
        category=category,
        severity="llm",
        confidence=0.55,
        title=title,
        detail=f"{title}: {detail}",
        related_pages=[],
        suggestion=None,
    )


def dedupe_issues(issues: list[LintIssue]) -> list[LintIssue]:
    seen: set[str] = set()
    deduped: list[LintIssue] = []
    for issue in issues:
        if issue.issue_id in seen:
            continue
        seen.add(issue.issue_id)
        deduped.append(issue)
    return deduped


def build_changes(items: list[tuple[Path, str]]) -> list[FileChange]:
    return [FileChange(path=path, before=path.read_text(encoding="utf-8") if path.exists() else None, after=after) for path, after in items]


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


def page_from_content(path: Path, content: str):
    from .markdown import parse_frontmatter
    from .models import PageFrontmatter, WikiPage

    frontmatter_data, body = parse_frontmatter(content)
    return WikiPage(path=str(path), frontmatter=PageFrontmatter.model_validate(frontmatter_data), body=body)


def slugify_title(title: str) -> str:
    return "-".join(filter(None, "".join(ch.lower() if ch.isalnum() else "-" for ch in title).split("-")))
