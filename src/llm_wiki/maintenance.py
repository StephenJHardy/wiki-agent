from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import DEFAULT_VAULT_DIRNAME, resolve_state_root, resolve_vault_root, resolve_wiki_root
from .filesystem import read_json
from .ingest import IngestResult, ingest_source
from .llm.prompts import load_prompt_context
from .models import SourceRecord, SourceRegistry
from .planning import ChangePlan, FileChange, OperationArtifact, OperationMetadata, apply_change_plan, save_operation_artifact
from .wiki import collect_wiki_pages, render_index, render_log_with_entry


@dataclass(slots=True)
class RefreshSourcesResult:
    requested_source_ids: list[str]
    refreshed: list[IngestResult] = field(default_factory=list)
    missing_source_ids: list[str] = field(default_factory=list)
    dry_run: bool = False


@dataclass(slots=True)
class IndexRebuildResult:
    change_plan: ChangePlan
    artifact_path: Path
    dry_run: bool


def refresh_sources(
    *,
    base_path: Path,
    source_id: str | None = None,
    refresh_all: bool = False,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    use_llm: bool = True,
    provider_name: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
    max_file_changes: int | None = None,
) -> RefreshSourcesResult:
    if refresh_all == bool(source_id):
        raise ValueError("Pass exactly one of `source_id` or `--all`.")

    state_root = resolve_state_root(base_path, vault_name)
    registry = SourceRegistry.model_validate(read_json(state_root / "sources.json"))
    records = registry.sources if refresh_all else [record for record in registry.sources if record.source_id == source_id]
    requested_ids = [record.source_id for record in registry.sources] if refresh_all else [source_id or ""]
    missing_ids = [] if records else requested_ids

    refreshed: list[IngestResult] = []
    for record in records:
        refreshed.append(
            refresh_source_record(
                base_path=base_path,
                record=record,
                vault_name=vault_name,
                use_llm=use_llm,
                provider_name=provider_name,
                model=model,
                dry_run=dry_run,
                max_file_changes=max_file_changes,
            )
        )

    return RefreshSourcesResult(
        requested_source_ids=requested_ids,
        refreshed=refreshed,
        missing_source_ids=missing_ids,
        dry_run=dry_run,
    )


def refresh_source_record(
    *,
    base_path: Path,
    record: SourceRecord,
    vault_name: str,
    use_llm: bool,
    provider_name: str | None,
    model: str | None,
    dry_run: bool,
    max_file_changes: int | None,
) -> IngestResult:
    return ingest_source(
        base_path=base_path,
        source_arg=str(resolve_vault_root(base_path, vault_name) / record.path),
        vault_name=vault_name,
        operation="refresh",
        use_llm=use_llm,
        provider_name=provider_name,
        model=model,
        dry_run=dry_run,
        max_file_changes=max_file_changes,
    )


def rebuild_wiki_index(
    *,
    base_path: Path,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
    dry_run: bool = False,
    max_file_changes: int | None = None,
) -> IndexRebuildResult:
    wiki_root = resolve_wiki_root(base_path, vault_name)
    state_root = resolve_state_root(base_path, vault_name)
    _, schema_bundle = load_prompt_context(base_path=base_path, vault_name=vault_name)

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = OperationMetadata(
        timestamp=timestamp,
        operation="rebuild-index",
        schema_domain=schema_bundle.config.domain,
        prompt_versions=schema_bundle.config.prompt_versions,
    )

    pages = collect_wiki_pages(wiki_root)
    index_after = render_index(wiki_root=wiki_root, pages=pages)
    detail_lines = [
        f"- Pages indexed: {len(pages)}",
        f"- Source pages: {sum(1 for page in pages if page.frontmatter.type == 'source')}",
        f"- Entity pages: {sum(1 for page in pages if page.frontmatter.type == 'entity')}",
        f"- Concept pages: {sum(1 for page in pages if page.frontmatter.type == 'concept')}",
        f"- Analysis pages: {sum(1 for page in pages if page.frontmatter.type == 'analysis')}",
    ]
    log_after = render_log_with_entry(
        existing=(wiki_root / "log.md").read_text(encoding="utf-8").rstrip(),
        operation="rebuild-index",
        title="Wiki index",
        detail_lines=detail_lines,
    )

    plan = ChangePlan(
        operation="rebuild-index",
        title="Wiki index",
        metadata=metadata,
        detail_lines=detail_lines,
        changes=[
            file_change(wiki_root / "index.md", index_after),
            file_change(wiki_root / "log.md", log_after),
        ],
    )
    plan.validate(max_file_changes=max_file_changes)
    if not dry_run:
        apply_change_plan(plan)

    artifact_path = save_operation_artifact(
        state_root=state_root,
        artifact=OperationArtifact(
            metadata=metadata,
            details={"page_count": len(pages)},
            change_summary={
                "file_changes": len(plan.changed_files()),
                "dry_run": dry_run,
            },
        ),
    )
    return IndexRebuildResult(change_plan=plan, artifact_path=artifact_path, dry_run=dry_run)


def file_change(path: Path, after: str) -> FileChange:
    before = path.read_text(encoding="utf-8") if path.exists() else None
    return FileChange(path=path, before=before, after=after)
