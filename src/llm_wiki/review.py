from __future__ import annotations

from pathlib import Path

from .planning import ChangePlan, render_change_plan_preview


def preview_change_plan(plan: ChangePlan, *, repo_root: Path | None = None) -> str:
    return render_change_plan_preview(plan, repo_root=repo_root)
