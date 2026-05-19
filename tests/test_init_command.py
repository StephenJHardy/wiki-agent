from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_wiki.cli import app

runner = CliRunner()


def test_init_creates_expected_files(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "vault/wiki/index.md").exists()
    assert (tmp_path / "vault/wiki/log.md").exists()
    assert (tmp_path / "vault/state/sources.json").exists()
    assert (tmp_path / "vault/state/claims.json").exists()
    assert (tmp_path / "vault/state/extracted").is_dir()
    assert (tmp_path / "vault/state/issues").is_dir()
    assert (tmp_path / "vault/state/operations").is_dir()
    assert (tmp_path / "vault/state/reviews/pending").is_dir()
    assert (tmp_path / "vault/state/reviews/applied").is_dir()
    assert (tmp_path / "vault/state/reviews/rejected").is_dir()
    assert (tmp_path / "vault/schema/config.yaml").exists()
    assert (tmp_path / "vault/schema/prompts/query.md").exists()
    assert (tmp_path / "vault/schema/templates/source.md").exists()
