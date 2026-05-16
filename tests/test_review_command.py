from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def pending_review_ids(base_path: Path) -> list[str]:
    return [path.stem for path in sorted((base_path / "vault/state/reviews/pending").glob("*.json"))]


def test_ingest_review_can_be_listed_shown_and_applied(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/reviewed.md"
    source_path.write_text("# Reviewed Source\n\nOpenAI studies review queues.", encoding="utf-8")

    result = runner.invoke(app, ["ingest", "reviewed.md", "--path", str(tmp_path), "--no-llm", "--review"])

    assert result.exit_code == 0
    assert "Saved pending review" in result.stdout
    assert not (tmp_path / "vault/wiki/sources/reviewed.md").exists()

    review_ids = pending_review_ids(tmp_path)
    assert len(review_ids) == 1
    review_id = review_ids[0]

    payload = json.loads((tmp_path / f"vault/state/reviews/pending/{review_id}.json").read_text(encoding="utf-8"))
    assert payload["operation"] == "ingest"
    assert payload["status"] == "pending"
    assert any(change["path"] == "vault/wiki/sources/reviewed.md" for change in payload["changes"])

    list_result = runner.invoke(app, ["review", "list", "--path", str(tmp_path)])
    assert list_result.exit_code == 0
    assert review_id in list_result.stdout

    show_result = runner.invoke(app, ["review", "show", review_id, "--path", str(tmp_path)])
    assert show_result.exit_code == 0
    assert "Reviewed Source" in show_result.stdout
    assert "vault/wiki/sources/reviewed.md" in show_result.stdout

    apply_result = runner.invoke(app, ["review", "apply", review_id, "--path", str(tmp_path)])
    assert apply_result.exit_code == 0
    assert "Applied review" in apply_result.stdout
    assert (tmp_path / "vault/wiki/sources/reviewed.md").exists()
    assert not (tmp_path / f"vault/state/reviews/pending/{review_id}.json").exists()
    assert (tmp_path / f"vault/state/reviews/applied/{review_id}.json").exists()


def test_review_apply_rejects_stale_plans(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/stale.md"
    source_path.write_text("# Stale Source\n\nOpenAI studies stale reviews.", encoding="utf-8")
    assert runner.invoke(app, ["ingest", "stale.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    source_path.write_text("# Stale Source\n\nAuthors: Ada Lovelace\n\nOpenAI studies stale reviews.", encoding="utf-8")
    review_result = runner.invoke(app, ["refresh-source", "stale", "--path", str(tmp_path), "--no-llm", "--review"])
    assert review_result.exit_code == 0
    review_id = pending_review_ids(tmp_path)[0]

    source_page_path = tmp_path / "vault/wiki/sources/stale.md"
    source_page_path.write_text(source_page_path.read_text(encoding="utf-8") + "\nManual edit.\n", encoding="utf-8")

    apply_result = runner.invoke(app, ["review", "apply", review_id, "--path", str(tmp_path)])

    assert apply_result.exit_code == 2
    assert "Cannot apply review" in apply_result.output
    assert (tmp_path / f"vault/state/reviews/pending/{review_id}.json").exists()


def test_review_reject_moves_pending_plan_without_applying(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    source_path = tmp_path / "vault/raw/sources/rejected.md"
    source_path.write_text("# Rejected Source\n\nOpenAI studies rejected reviews.", encoding="utf-8")

    result = runner.invoke(app, ["ingest", "rejected.md", "--path", str(tmp_path), "--no-llm", "--review"])
    assert result.exit_code == 0
    review_id = pending_review_ids(tmp_path)[0]

    reject_result = runner.invoke(app, ["review", "reject", review_id, "--path", str(tmp_path)])

    assert reject_result.exit_code == 0
    assert "Rejected review" in reject_result.stdout
    assert not (tmp_path / "vault/wiki/sources/rejected.md").exists()
    assert not (tmp_path / f"vault/state/reviews/pending/{review_id}.json").exists()
    assert (tmp_path / f"vault/state/reviews/rejected/{review_id}.json").exists()
