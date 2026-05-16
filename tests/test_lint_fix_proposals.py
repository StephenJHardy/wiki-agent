from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def load_pending_reviews(base_path: Path) -> list[dict[str, object]]:
    reviews = []
    for path in sorted((base_path / "vault/state/reviews/pending").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_path"] = path
        reviews.append(payload)
    return reviews


def find_review(base_path: Path, title: str) -> dict[str, object]:
    for review in load_pending_reviews(base_path):
        if review["title"] == title:
            return review
    raise AssertionError(f"Review not found: {title}")


def write_concept_page(path: Path, *, title: str, body: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"title: {title}",
                "type: concept",
                "updated_at: '2026-04-05T20:00:00+10:00'",
                "source_ids:",
                "- sample",
                "---",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


def test_lint_proposes_reviewable_index_fix(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    write_concept_page(
        tmp_path / "vault/wiki/concepts/manual.md",
        title="Manual Concept",
        body="## Concept Summary\nManual Concept is missing from the index.\n\n## Claim Timeline\n- Existing timeline.",
    )

    result = runner.invoke(app, ["lint", "--path", str(tmp_path), "--no-llm", "--propose-fixes", "--review"])

    assert result.exit_code == 0
    assert "Proposed" in result.stdout
    review = find_review(tmp_path, "Rebuild index coverage")
    review_id = str(review["review_id"])

    assert any(change["path"] == "vault/wiki/index.md" for change in review["changes"])
    assert "[[Manual Concept]]" not in (tmp_path / "vault/wiki/index.md").read_text(encoding="utf-8")

    apply_result = runner.invoke(app, ["review", "apply", review_id, "--path", str(tmp_path)])

    assert apply_result.exit_code == 0
    assert "[[Manual Concept]]" in (tmp_path / "vault/wiki/index.md").read_text(encoding="utf-8")


def test_lint_proposes_reviewable_claim_timeline_fix(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    write_concept_page(
        tmp_path / "vault/wiki/concepts/timeline.md",
        title="Timeline Concept",
        body="## Concept Summary\nTimeline Concept has no timeline section.",
    )

    result = runner.invoke(app, ["lint", "--path", str(tmp_path), "--no-llm", "--propose-fixes", "--review"])

    assert result.exit_code == 0
    review = find_review(tmp_path, "Add missing claim timeline sections")
    review_id = str(review["review_id"])

    apply_result = runner.invoke(app, ["review", "apply", review_id, "--path", str(tmp_path)])

    assert apply_result.exit_code == 0
    page_text = (tmp_path / "vault/wiki/concepts/timeline.md").read_text(encoding="utf-8")
    assert "## Claim Timeline" in page_text
    assert "refresh-source" in page_text


def test_lint_proposes_obvious_broken_link_casing_fix(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    write_concept_page(
        tmp_path / "vault/wiki/concepts/target.md",
        title="Target Concept",
        body="## Concept Summary\nTarget Concept is the real page.\n\n## Claim Timeline\n- Existing timeline.",
    )
    write_concept_page(
        tmp_path / "vault/wiki/concepts/source.md",
        title="Source Concept",
        body="## Concept Summary\nSource links to [[target concept]].\n\n## Claim Timeline\n- Existing timeline.",
    )

    result = runner.invoke(app, ["lint", "--path", str(tmp_path), "--no-llm", "--propose-fixes", "--review"])

    assert result.exit_code == 0
    review = find_review(tmp_path, "Fix obvious broken wiki-link casing")
    review_id = str(review["review_id"])

    apply_result = runner.invoke(app, ["review", "apply", review_id, "--path", str(tmp_path)])

    assert apply_result.exit_code == 0
    source_text = (tmp_path / "vault/wiki/concepts/source.md").read_text(encoding="utf-8")
    assert "[[Target Concept]]" in source_text
    assert "[[target concept]]" not in source_text
