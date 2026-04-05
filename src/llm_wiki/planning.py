from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .diffing import render_unified_diff
from .filesystem import ensure_directory


class OperationMetadata(BaseModel):
    timestamp: str
    operation: str
    schema_domain: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    llm_requested: bool = False
    llm_used: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    raw_source_fallback: bool = False
    retrieval_traces: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OperationArtifact(BaseModel):
    metadata: OperationMetadata
    details: dict[str, Any] = Field(default_factory=dict)
    change_summary: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class FileChange:
    path: Path
    after: str
    before: str | None = None

    @property
    def kind(self) -> str:
        if self.before is None:
            return "create"
        if self.before == self.after:
            return "unchanged"
        return "update"

    def diff(self) -> str:
        return render_unified_diff(path=self.path, before=self.before, after=self.after)


@dataclass(slots=True)
class ChangePlan:
    operation: str
    title: str
    metadata: OperationMetadata
    detail_lines: list[str] = field(default_factory=list)
    changes: list[FileChange] = field(default_factory=list)

    def changed_files(self) -> list[FileChange]:
        return [change for change in self.changes if change.before != change.after]

    def validate(self, *, max_file_changes: int | None = None) -> None:
        changed_files = self.changed_files()
        if max_file_changes is not None and len(changed_files) > max_file_changes:
            raise ValueError(
                f"Planned {len(changed_files)} file changes for {self.operation}, "
                f"which exceeds the limit of {max_file_changes}."
            )


def apply_change_plan(plan: ChangePlan) -> list[Path]:
    written: list[Path] = []
    for change in plan.changed_files():
        ensure_directory(change.path.parent)
        change.path.write_text(change.after, encoding="utf-8")
        written.append(change.path)
    return written


def render_change_plan_preview(plan: ChangePlan, *, repo_root: Path | None = None) -> str:
    changed_files = plan.changed_files()
    lines = [
        "# Change Plan",
        "",
        f"Operation: {plan.operation}",
        f"Title: {plan.title}",
        f"Files changed: {len(changed_files)}",
    ]
    if plan.metadata.llm_requested:
        llm_status = "used" if plan.metadata.llm_used else "requested but not used"
        llm_label = plan.metadata.llm_provider or "unknown"
        if plan.metadata.llm_model:
            llm_label = f"{llm_label}:{plan.metadata.llm_model}"
        lines.append(f"LLM: {llm_status} ({llm_label})")
    if plan.metadata.schema_domain:
        lines.append(f"Schema domain: {plan.metadata.schema_domain}")
    if plan.metadata.prompt_versions:
        prompt_versions = ", ".join(f"{name}={version}" for name, version in sorted(plan.metadata.prompt_versions.items()))
        lines.append(f"Prompt versions: {prompt_versions}")
    if plan.metadata.raw_source_fallback:
        lines.append("Raw-source fallback: triggered")
    if plan.detail_lines:
        lines.extend(["", "## Details"])
        lines.extend(plan.detail_lines)
    if not changed_files:
        lines.extend(["", "## Diffs", "- No file changes."])
        return "\n".join(lines)

    lines.extend(["", "## Diffs"])
    for change in changed_files:
        display_path = change.path if repo_root is None else change.path.relative_to(repo_root)
        lines.extend(["", f"### {change.kind}: {display_path.as_posix()}"])
        diff_text = change.diff()
        if diff_text:
            lines.extend(["```diff", diff_text, "```"])
        else:
            lines.append("No textual diff.")
    return "\n".join(lines)


def save_operation_artifact(
    *,
    state_root: Path,
    artifact: OperationArtifact,
) -> Path:
    operations_root = state_root / "operations"
    ensure_directory(operations_root)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    target = operations_root / f"{stamp}-{artifact.metadata.operation}.json"
    target.write_text(json.dumps(artifact.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
