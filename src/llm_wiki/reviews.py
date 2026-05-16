from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .filesystem import ensure_directory, slugify
from .planning import ChangePlan, FileChange, OperationMetadata, apply_change_plan

REVIEW_STATES = ("pending", "applied", "rejected")


class ReviewFileChange(BaseModel):
    path: str
    before: str | None = None
    after: str


class ReviewPlanPayload(BaseModel):
    review_id: str
    status: str = "pending"
    created_at: str
    updated_at: str
    operation: str
    title: str
    metadata: OperationMetadata
    detail_lines: list[str] = Field(default_factory=list)
    changes: list[ReviewFileChange] = Field(default_factory=list)


@dataclass(slots=True)
class ReviewPlan:
    payload: ReviewPlanPayload
    path: Path

    @property
    def review_id(self) -> str:
        return self.payload.review_id

    @property
    def status(self) -> str:
        return self.payload.status


def reviews_root(*, state_root: Path) -> Path:
    return state_root / "reviews"


def review_state_root(*, state_root: Path, status: str) -> Path:
    if status not in REVIEW_STATES:
        raise ValueError(f"Unknown review status: {status}")
    return reviews_root(state_root=state_root) / status


def save_pending_review(*, state_root: Path, plan: ChangePlan, repo_root: Path) -> ReviewPlan:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    review_id = build_review_id(plan)
    payload = ReviewPlanPayload(
        review_id=review_id,
        status="pending",
        created_at=now,
        updated_at=now,
        operation=plan.operation,
        title=plan.title,
        metadata=plan.metadata,
        detail_lines=plan.detail_lines,
        changes=[
            ReviewFileChange(
                path=serialize_path(change.path, repo_root=repo_root),
                before=change.before,
                after=change.after,
            )
            for change in plan.changed_files()
        ],
    )
    target = review_state_root(state_root=state_root, status="pending") / f"{review_id}.json"
    ensure_directory(target.parent)
    target.write_text(json.dumps(payload.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ReviewPlan(payload=payload, path=target)


def list_reviews(*, state_root: Path, status: str = "pending") -> list[ReviewPlan]:
    root = review_state_root(state_root=state_root, status=status)
    if not root.exists():
        return []
    reviews = [load_review_path(path) for path in sorted(root.glob("*.json"))]
    reviews.sort(key=lambda review: review.payload.created_at)
    return reviews


def load_review(*, state_root: Path, review_id: str, status: str | None = None) -> ReviewPlan:
    statuses = [status] if status is not None else list(REVIEW_STATES)
    for candidate_status in statuses:
        path = review_state_root(state_root=state_root, status=candidate_status) / f"{review_id}.json"
        if path.exists():
            return load_review_path(path)
    raise FileNotFoundError(f"Review not found: {review_id}")


def load_review_path(path: Path) -> ReviewPlan:
    payload = ReviewPlanPayload.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return ReviewPlan(payload=payload, path=path)


def review_to_change_plan(review: ReviewPlan, *, repo_root: Path) -> ChangePlan:
    return ChangePlan(
        operation=review.payload.operation,
        title=review.payload.title,
        metadata=review.payload.metadata,
        detail_lines=review.payload.detail_lines,
        changes=[
            FileChange(
                path=deserialize_path(change.path, repo_root=repo_root),
                before=change.before,
                after=change.after,
            )
            for change in review.payload.changes
        ],
    )


def apply_review(*, state_root: Path, repo_root: Path, review_id: str) -> ReviewPlan:
    review = load_review(state_root=state_root, review_id=review_id, status="pending")
    plan = review_to_change_plan(review, repo_root=repo_root)
    validate_review_is_current(plan)
    apply_change_plan(plan)
    return move_review(state_root=state_root, review=review, status="applied")


def reject_review(*, state_root: Path, review_id: str) -> ReviewPlan:
    review = load_review(state_root=state_root, review_id=review_id, status="pending")
    return move_review(state_root=state_root, review=review, status="rejected")


def validate_review_is_current(plan: ChangePlan) -> None:
    for change in plan.changed_files():
        if change.before is None:
            if change.path.exists():
                raise ValueError(f"Cannot apply review because `{change.path}` now exists.")
            continue
        if not change.path.exists():
            raise ValueError(f"Cannot apply review because `{change.path}` no longer exists.")
        current = change.path.read_text(encoding="utf-8")
        if current != change.before:
            raise ValueError(f"Cannot apply review because a file has changed since the review was created: `{change.path}`.")


def move_review(*, state_root: Path, review: ReviewPlan, status: str) -> ReviewPlan:
    if status not in {"applied", "rejected"}:
        raise ValueError(f"Unsupported terminal review status: {status}")
    payload = review.payload.model_copy(
        update={
            "status": status,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    )
    target = review_state_root(state_root=state_root, status=status) / review.path.name
    ensure_directory(target.parent)
    target.write_text(json.dumps(payload.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review.path.unlink()
    return ReviewPlan(payload=payload, path=target)


def build_review_id(plan: ChangePlan) -> str:
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f")
    return slugify(f"{stamp}-{plan.operation}-{plan.title}")[:120]


def serialize_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def deserialize_path(path: str, *, repo_root: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate
