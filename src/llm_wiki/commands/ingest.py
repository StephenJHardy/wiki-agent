from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME, resolve_state_root
from ..ingest import ingest_source
from ..review import preview_change_plan
from ..reviews import save_pending_review


def ingest_command(
    source: str = typer.Argument(
        ...,
        help="Local source path, source name under `vault/raw/sources/`, or an HTTP(S) URL to snapshot locally.",
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
        help="Preview planned file changes without writing them.",
    ),
    review: bool = typer.Option(
        False,
        "--review",
        help="Save the planned file changes for later review instead of applying them.",
    ),
    max_file_changes: int | None = typer.Option(
        20,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed for this operation.",
    ),
) -> None:
    """Ingest a local or remote source into the wiki."""

    console = Console()
    try:
        result = ingest_source(
            base_path=path,
            source_arg=source,
            vault_name=vault_name,
            use_llm=use_llm,
            provider_name=provider,
            model=model,
            dry_run=dry_run or review,
            max_file_changes=max_file_changes,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Ingested [bold]{result.analysis.title}[/bold] as `{result.source_record.source_id}`")
    console.print(f"Planned {len(result.change_plan.changed_files())} file change(s).")
    console.print(preview_change_plan(result.change_plan, repo_root=path), markup=False)
    if review:
        saved_review = save_pending_review(
            state_root=resolve_state_root(path, vault_name),
            plan=result.change_plan,
            repo_root=path,
        )
        console.print(f"Saved pending review `{saved_review.review_id}`.")
    elif result.dry_run:
        console.print("Dry run only. No files were written.")
    else:
        console.print(f"Updated {len(set(result.updated_pages))} wiki page(s).")
    console.print(f"Saved operation artifact at [bold]{result.artifact_path}[/bold]")
