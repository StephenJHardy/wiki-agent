from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ..config import DEFAULT_VAULT_DIRNAME, resolve_state_root
from ..lint import propose_lint_fix_plans, run_lint
from ..review import preview_change_plan
from ..reviews import save_pending_review


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
    propose_fixes: bool = typer.Option(
        False,
        "--propose-fixes",
        help="Build conservative fix plans for lint issues without applying them.",
    ),
    review: bool = typer.Option(
        False,
        "--review",
        help="Save proposed lint fixes for later review.",
    ),
    max_file_changes: int | None = typer.Option(
        10,
        "--max-file-changes",
        min=1,
        help="Maximum number of file changes allowed for lint output.",
    ),
) -> None:
    """Run a health check over the wiki."""

    if review and not propose_fixes:
        raise typer.BadParameter("`--review` currently requires `--propose-fixes` for lint.")

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

    if propose_fixes:
        try:
            fix_plans = propose_lint_fix_plans(
                base_path=path,
                issues=result.issues,
                vault_name=vault_name,
                max_file_changes=max_file_changes,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        if not fix_plans:
            console.print("No conservative lint fixes could be proposed.")
            return

        console.print(f"Proposed {len(fix_plans)} lint fix plan(s).")
        for plan in fix_plans:
            console.print(preview_change_plan(plan, repo_root=path), markup=False)
            if review:
                saved_review = save_pending_review(
                    state_root=resolve_state_root(path, vault_name),
                    plan=plan,
                    repo_root=path,
                )
                console.print(f"Saved pending review `{saved_review.review_id}`.")
