from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from ..config import DEFAULT_VAULT_DIRNAME
from ..viewer import create_viewer_app


def view_command(
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
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind the viewer to."),
    port: int = typer.Option(8421, "--port", help="Port to bind the viewer to."),
    reload: bool = typer.Option(False, "--reload/--no-reload", help="Enable live reload for development."),
) -> None:
    """Launch the FastHTML wiki viewer."""

    app = create_viewer_app(base_path=path, vault_name=vault_name)
    uvicorn.run(app, host=host, port=port, reload=reload)
