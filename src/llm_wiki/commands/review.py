from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME, resolve_state_root
from ..review import preview_change_plan
from ..reviews import REVIEW_STATES, apply_review, list_reviews, load_review, reject_review, review_to_change_plan

review_app = typer.Typer(
    add_completion=False,
    help="Review, apply, or reject saved change plans.",
    no_args_is_help=True,
)


@review_app.command("list")
def review_list_command(
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
    status: str = typer.Option(
        "pending",
        "--status",
        help=f"Review status to list: {', '.join(REVIEW_STATES)}.",
    ),
) -> None:
    """List saved review plans."""

    console = Console()
    state_root = resolve_state_root(path, vault_name)
    try:
        reviews = list_reviews(state_root=state_root, status=status)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if not reviews:
        console.print(f"No {status} reviews.")
        return

    for review in reviews:
        console.print(
            f"{review.review_id} | {review.payload.operation} | "
            f"{review.payload.title} | files: {len(review.payload.changes)}"
        )


@review_app.command("show")
def review_show_command(
    review_id: str = typer.Argument(..., help="Review ID to inspect."),
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
) -> None:
    """Show a saved review plan and its diffs."""

    console = Console()
    state_root = resolve_state_root(path, vault_name)
    try:
        review = load_review(state_root=state_root, review_id=review_id)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    plan = review_to_change_plan(review, repo_root=path)
    console.print(preview_change_plan(plan, repo_root=path), markup=False)


@review_app.command("apply")
def review_apply_command(
    review_id: str = typer.Argument(..., help="Pending review ID to apply."),
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
) -> None:
    """Apply a pending review plan."""

    console = Console()
    state_root = resolve_state_root(path, vault_name)
    try:
        review = apply_review(state_root=state_root, repo_root=path, review_id=review_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Applied review `{review.review_id}`.")


@review_app.command("reject")
def review_reject_command(
    review_id: str = typer.Argument(..., help="Pending review ID to reject."),
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
) -> None:
    """Reject a pending review plan without applying it."""

    console = Console()
    state_root = resolve_state_root(path, vault_name)
    try:
        review = reject_review(state_root=state_root, review_id=review_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Rejected review `{review.review_id}`.")
