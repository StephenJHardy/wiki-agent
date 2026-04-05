from __future__ import annotations

from difflib import unified_diff
from pathlib import Path


def render_unified_diff(*, path: Path, before: str | None, after: str) -> str:
    before_lines = [] if before is None else before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path.as_posix()}",
        tofile=f"b/{path.as_posix()}",
    )
    return "".join(diff).strip()
