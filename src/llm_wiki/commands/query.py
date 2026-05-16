from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME, resolve_state_root
from ..query import run_query
from ..review import preview_change_plan
from ..reviews import save_pending_review


def query_command(
    question: str = typer.Argument(..., help="Question to answer from the wiki."),
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
    file_answer: bool = typer.Option(
        False,
        "--file/--no-file",
        help="Persist the answer into `vault/wiki/analyses/`.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional title to use when filing the answer.",
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
        help="Preview filed analysis changes without writing them.",
    ),
    review: bool = typer.Option(
        False,
        "--review",
        help="Save filed analysis changes for later review instead of applying them.",
    ),
    max_file_changes: int | None = typer.Option(
        10,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed if the answer is filed.",
    ),
) -> None:
    """Answer a question from the maintained wiki."""

    if review and not file_answer:
        raise typer.BadParameter("`--review` requires `--file` so there is a change plan to save.")

    console = Console()
    result = run_query(
        base_path=path,
        question=question,
        vault_name=vault_name,
        file_answer=file_answer,
        title=title,
        use_llm=use_llm,
        provider_name=provider,
        model=model,
        dry_run=dry_run or review,
        max_file_changes=max_file_changes,
    )
    console.print(result.answer_markdown, markup=False)
    if result.change_plan.changed_files():
        console.print(preview_change_plan(result.change_plan, repo_root=path), markup=False)
    if review and result.change_plan.changed_files():
        saved_review = save_pending_review(
            state_root=resolve_state_root(path, vault_name),
            plan=result.change_plan,
            repo_root=path,
        )
        console.print(f"Saved pending review `{saved_review.review_id}`.")
    elif result.written_page is not None and not result.dry_run:
        console.print(f"Filed analysis at [bold]{result.written_page}[/bold]")
    elif result.written_page is not None and result.dry_run:
        console.print("Dry run only. No files were written.")
    console.print(f"Saved operation artifact at [bold]{result.artifact_path}[/bold]")
