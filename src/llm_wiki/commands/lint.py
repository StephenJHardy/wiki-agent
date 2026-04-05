from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME
from ..lint import run_lint
from ..review import preview_change_plan


def lint_command(
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
    file_report: bool = typer.Option(
        False,
        "--file/--no-file",
        help="Persist the lint report into `vault/wiki/analyses/`.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional title to use when filing the lint report.",
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
        help="Preview lint report and issue-state changes without writing them.",
    ),
    max_file_changes: int | None = typer.Option(
        10,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed for lint output.",
    ),
) -> None:
    """Run a health check over the wiki."""

    console = Console()
    result = run_lint(
        base_path=path,
        vault_name=vault_name,
        file_report=file_report,
        title=title,
        use_llm=use_llm,
        provider_name=provider,
        model=model,
        dry_run=dry_run,
        max_file_changes=max_file_changes,
    )
    console.print(result.report_markdown, markup=False)
    if result.change_plan.changed_files():
        console.print(preview_change_plan(result.change_plan, repo_root=path), markup=False)
    if result.written_page is not None and not result.dry_run:
        console.print(f"Filed lint report at [bold]{result.written_page}[/bold]")
    elif result.written_page is not None and result.dry_run:
        console.print("Dry run only. No files were written.")
    console.print(f"Saved operation artifact at [bold]{result.artifact_path}[/bold]")
