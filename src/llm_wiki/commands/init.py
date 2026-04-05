from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME, VAULT_DIRECTORIES, resolve_vault_root
from ..filesystem import ensure_directory, write_json, write_text
from ..templates import (
    SUPPORTED_DOMAINS,
    agents_template,
    index_template,
    log_template,
    schema_config_template,
    schema_prompt_templates,
    sources_state_template,
)


def init_command(
    path: Path = typer.Argument(
        Path("."),
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
        help="Directory where the wiki vault should be created.",
    ),
    vault_name: str = typer.Option(
        DEFAULT_VAULT_DIRNAME,
        "--vault-name",
        help="Name of the vault directory to create.",
    ),
    domain: str = typer.Option(
        "general",
        "--domain",
        help=f"Domain schema to scaffold. Supported: {', '.join(SUPPORTED_DOMAINS)}.",
    ),
) -> None:
    """Create the starter vault structure and guide files."""

    console = Console()
    vault_root = resolve_vault_root(path, vault_name)
    if domain not in SUPPORTED_DOMAINS:
        raise typer.BadParameter(f"Unsupported domain: {domain}")

    for relative_dir in VAULT_DIRECTORIES:
        ensure_directory(vault_root / relative_dir)

    write_text(path / "AGENTS.md", agents_template())
    write_text(vault_root / "wiki/index.md", index_template())
    write_text(vault_root / "wiki/log.md", log_template())
    write_json(vault_root / "state/sources.json", sources_state_template())
    write_text(vault_root / "schema/config.yaml", schema_config_template(domain))
    schema_files = schema_prompt_templates(domain)
    for filename, contents in schema_files.items():
        parent = "prompts" if filename.endswith(".md") and filename in {"common.md", "ingest.md", "query.md", "lint.md"} else "templates"
        write_text(vault_root / "schema" / parent / filename, contents)

    console.print(f"Initialized LLM Wiki vault at [bold]{vault_root}[/bold]")
