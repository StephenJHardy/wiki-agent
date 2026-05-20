from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient
from typer.testing import CliRunner

from llm_wiki.cli import app
from llm_wiki.viewer import create_viewer_app, render_markdown_with_math

runner = CliRunner()


def test_render_markdown_with_math_preserves_latex_and_wiki_links() -> None:
    html = render_markdown_with_math(
        "See [[Euler]] and inline math $a_b + c$.\n\n$$x^2 + y^2 = z^2$$",
        title_index={"Euler": "euler"},
    )

    assert 'href="/page/euler"' in html
    assert "\\(a_b + c\\)" in html
    assert "\\[x^2 + y^2 = z^2\\]" in html


def test_viewer_page_route_renders_math_and_backlinks(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/math.md"
    source_path.write_text(
        "\n".join(
            [
                "# Euler Notes",
                "",
                "Euler studies graph theory and the handshake lemma.",
                "",
                "## Formula",
                "",
                "- The classic identity is $e^{i\\pi}+1=0$.",
            ]
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "math.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    concept_path = tmp_path / "vault/wiki/concepts/formula.md"
    concept_path.write_text(
        "\n".join(
            [
                "---",
                "title: Formula",
                "type: concept",
                "updated_at: '2026-04-05T20:00:00+10:00'",
                "source_ids:",
                "- math",
                "summary: Formula is linked to [[Euler Notes]].",
                "---",
                "",
                "## Concept Summary",
                "Formula links back to [[Euler Notes]].",
            ]
        ),
        encoding="utf-8",
    )

    client = TestClient(create_viewer_app(base_path=tmp_path))
    response = client.get("/page/euler-notes")

    assert response.status_code == 200
    assert "Euler Notes" in response.text
    assert "MathJax-script" in response.text
    assert "\\(e^{i\\pi}+1=0\\)" in response.text


def test_viewer_search_route_uses_retrieval(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/retrieval.md"
    source_path.write_text(
        "\n".join(
            [
                "# Retrieval Augmented Generation",
                "",
                "RAG helps answer questions with external knowledge.",
                "",
                "## Retrieval",
                "",
                "- Retrieval improves grounded answers.",
            ]
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "retrieval.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    client = TestClient(create_viewer_app(base_path=tmp_path))
    response = client.get("/?q=RAG")

    assert response.status_code == 200
    assert "Search Results" in response.text
    assert "Retrieval Augmented Generation" in response.text


def test_viewer_exposes_issues_and_operations_routes(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/notes.md"
    source_path.write_text(
        "# Notes\n\nOpenAI discusses evaluation discipline, but the source page may become stale.",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "notes.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0
    assert runner.invoke(app, ["lint", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    client = TestClient(create_viewer_app(base_path=tmp_path))

    issues_response = client.get("/issues")
    operations_response = client.get("/operations")

    assert issues_response.status_code == 200
    assert "Maintenance Issues" in issues_response.text
    assert operations_response.status_code == 200
    assert "Operation Artifacts" in operations_response.text


def test_viewer_exposes_review_queue_and_review_detail(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/review.md"
    source_path.write_text("# Review Source\n\nOpenAI studies review queues.", encoding="utf-8")
    assert runner.invoke(app, ["ingest", "review.md", "--path", str(tmp_path), "--no-llm", "--review"]).exit_code == 0

    review_paths = sorted((tmp_path / "vault/state/reviews/pending").glob("*.json"))
    assert len(review_paths) == 1
    review_id = review_paths[0].stem

    client = TestClient(create_viewer_app(base_path=tmp_path))
    list_response = client.get("/reviews")
    detail_response = client.get(f"/reviews/{review_id}")

    assert list_response.status_code == 200
    assert "Review Queue" in list_response.text
    assert review_id in list_response.text
    assert "Review Source" in list_response.text

    assert detail_response.status_code == 200
    assert "Change Plan" in detail_response.text
    assert "vault/wiki/sources/review.md" in detail_response.text


def test_viewer_exposes_claim_timeline_sources_and_page_provenance(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    source_path = tmp_path / "vault/raw/sources/provenance.md"
    source_path.write_text(
        "\n".join(
            [
                "# Provenance Source",
                "",
                "Authors: Ada Lovelace",
                "Published: 2024-05-17",
                "",
                "OpenAI studies provenance for durable wiki systems.",
                "",
                "## Provenance",
                "",
                "- Claim provenance records who introduced an idea and when.",
            ]
        ),
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "provenance.md", "--path", str(tmp_path), "--no-llm"]).exit_code == 0

    client = TestClient(create_viewer_app(base_path=tmp_path))

    timeline_response = client.get("/timeline")
    source_response = client.get("/sources/provenance")
    page_response = client.get("/page/provenance/provenance")

    assert timeline_response.status_code == 200
    assert "Claim Timeline" in timeline_response.text
    assert "Claim provenance records who introduced an idea and when" in timeline_response.text

    assert source_response.status_code == 200
    assert "Provenance Source" in source_response.text
    assert "Published: 2024-05-17" in source_response.text

    assert page_response.status_code == 200
    assert "Provenance Provenance" in page_response.text
    assert "Source Lineage" in page_response.text
    assert "provenance" in page_response.text


def test_viewer_handles_empty_and_missing_provenance_states(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    client = TestClient(create_viewer_app(base_path=tmp_path))

    timeline_response = client.get("/timeline")
    missing_source_response = client.get("/sources/missing-source")
    missing_page_response = client.get("/page/missing-page/provenance")

    assert timeline_response.status_code == 200
    assert "No claim records yet." in timeline_response.text

    assert missing_source_response.status_code == 200
    assert "Source Not Found" in missing_source_response.text
    assert "missing-source" in missing_source_response.text

    assert missing_page_response.status_code == 200
    assert "Page Not Found" in missing_page_response.text
    assert "missing-page" in missing_page_response.text
