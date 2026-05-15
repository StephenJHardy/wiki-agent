from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..batch import ingest_directory
from ..config import DEFAULT_VAULT_DIRNAME


def ingest_dir_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
        help="Directory of local source files to copy into `vault/raw/sources/` and ingest.",
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
    recurse: bool = typer.Option(
        True,
        "--recurse/--no-recurse",
        help="Recursively scan the directory for supported source files.",
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
    max_file_changes: int | None = typer.Option(
        20,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed per ingested source.",
    ),
) -> None:
    """Copy a directory of local sources into the vault and ingest them."""

    console = Console()
    try:
        result = ingest_directory(
            base_path=path,
            directory=directory,
            vault_name=vault_name,
            recurse=recurse,
            use_llm=use_llm,
            provider_name=provider,
            model=model,
            max_file_changes=max_file_changes,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Imported {result.imported_count} supported source file(s) into `vault/raw/sources/`.")
    console.print(f"Ingested {result.ingested_count} source file(s).")
    if result.skipped_count:
        console.print(f"Skipped {result.skipped_count} file(s).")
        for item in result.items:
            if item.skipped_reason is not None:
                console.print(f"- {item.original_path.name}: {item.skipped_reason}")
