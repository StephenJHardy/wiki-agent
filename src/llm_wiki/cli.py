from __future__ import annotations

import typer

from .commands.init import init_command
from .commands.ingest import ingest_command
from .commands.ingest_dir import ingest_dir_command
from .commands.lint import lint_command
from .commands.query import query_command
from .commands.rebuild_index import rebuild_index_command
from .commands.refresh_source import refresh_source_command
from .commands.view import view_command

app = typer.Typer(
    add_completion=False,
    help="Build and maintain a persistent, filesystem-first LLM wiki.",
    no_args_is_help=True,
)

app.command("init")(init_command)
app.command("ingest")(ingest_command)
app.command("ingest-dir")(ingest_dir_command)
app.command("refresh-source")(refresh_source_command)
app.command("rebuild-index")(rebuild_index_command)
app.command("query")(query_command)
app.command("lint")(lint_command)
app.command("view")(view_command)


def main() -> None:
    app()
