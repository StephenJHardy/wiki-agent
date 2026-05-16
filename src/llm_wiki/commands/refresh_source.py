from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME
from ..maintenance import refresh_sources
from ..review import preview_change_plan


def refresh_source_command(
    source_id: str | None = typer.Argument(
        None,
        help="Source ID from `vault/state/sources.json` to refresh.",
    ),
    path: Path = typer.Option(
        Path("."),
        "--path",
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
        help="Repository root that contains the vault.",
    ),
    vault_name: str = typer.Option(
        DEFAULT_VAULT_DIRNAME,
        "--vault-name",
        help="Name of the vault directory.",
    ),
    refresh_all: bool = typer.Option(
        False,
        "--all",
        help="Refresh every registered source.",
    ),
    use_llm: bool = typer.Option(
        True,
        "--llm/--no-llm",
        help="Use a configured LLM provider when available.",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Override the configured LLM provider.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override the configured LLM model.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview refresh changes without writing wiki files.",
    ),
    max_file_changes: int | None = typer.Option(
        20,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed per refreshed source.",
    ),
) -> None:
    """Refresh registered sources to backfill metadata and generated pages."""

    console = Console()
    try:
        result = refresh_sources(
            base_path=path,
            source_id=source_id,
            refresh_all=refresh_all,
            vault_name=vault_name,
            use_llm=use_llm,
            provider_name=provider,
            model=model,
            dry_run=dry_run,
            max_file_changes=max_file_changes,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if result.missing_source_ids:
        raise typer.BadParameter(f"Source not found: {', '.join(result.missing_source_ids)}")

    console.print(f"Refreshed {len(result.refreshed)} source(s).")
    for refresh_result in result.refreshed:
        console.print(
            f"- `{refresh_result.source_record.source_id}`: "
            f"{len(refresh_result.change_plan.changed_files())} planned file change(s)."
        )
        console.print(preview_change_plan(refresh_result.change_plan, repo_root=path), markup=False)

    if result.dry_run:
        console.print("Dry run only. No wiki files were written.")
