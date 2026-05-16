from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME
from ..maintenance import rebuild_wiki_index
from ..review import preview_change_plan


def rebuild_index_command(
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview index/log changes without writing wiki files.",
    ),
    max_file_changes: int | None = typer.Option(
        2,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed.",
    ),
) -> None:
    """Rebuild `vault/wiki/index.md` from current wiki pages."""

    console = Console()
    result = rebuild_wiki_index(
        base_path=path,
        vault_name=vault_name,
        dry_run=dry_run,
        max_file_changes=max_file_changes,
    )
    console.print(preview_change_plan(result.change_plan, repo_root=path), markup=False)
    if result.dry_run:
        console.print("Dry run only. No wiki files were written.")
    console.print(f"Saved operation artifact at [bold]{result.artifact_path}[/bold]")
