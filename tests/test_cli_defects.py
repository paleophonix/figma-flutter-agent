"""Tests for ``figma-flutter defects`` CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from figma_flutter_agent.cli import app


def test_defects_validate_success() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["defects", "validate"])
    assert result.exit_code == 0, result.stdout
    assert "valid" in result.stdout


def _patch_corpus_paths(monkeypatch, *, families_file: Path, cases_directory: Path) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.defects.validation.families_path",
        lambda: families_file,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.defects.validation.cases_dir",
        lambda: cases_directory,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.defects.loader.families_path",
        lambda: families_file,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.defects.loader.cases_dir",
        lambda: cases_directory,
    )


def test_defects_validate_invalid_yaml(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus"
    cases = corpus / "cases"
    cases.mkdir(parents=True)
    (corpus / "families.yaml").write_text("version: 1\nfamilies: []\n", encoding="utf-8")
    (cases / "bad.yaml").write_text("case:\n  id: [unclosed\n", encoding="utf-8")
    _patch_corpus_paths(monkeypatch, families_file=corpus / "families.yaml", cases_directory=cases)
    runner = CliRunner()
    result = runner.invoke(app, ["defects", "validate"])
    assert result.exit_code == 1
    assert "YAML parse error" in result.stdout
    assert "Traceback" not in result.stdout


def test_defects_validate_missing_families(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _patch_corpus_paths(
        monkeypatch,
        families_file=corpus / "families.yaml",
        cases_directory=corpus / "cases",
    )
    runner = CliRunner()
    result = runner.invoke(app, ["defects", "validate"])
    assert result.exit_code == 1
    assert "families file not found" in result.stdout
    assert "Traceback" not in result.stdout


def test_defects_validate_schema_error(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus"
    cases = corpus / "cases"
    cases.mkdir(parents=True)
    (corpus / "families.yaml").write_text(
        "version: 1\nfamilies:\n  - id: bad id\n",
        encoding="utf-8",
    )
    _patch_corpus_paths(monkeypatch, families_file=corpus / "families.yaml", cases_directory=cases)
    runner = CliRunner()
    result = runner.invoke(app, ["defects", "validate"])
    assert result.exit_code == 1
    assert "families.yaml" in result.stdout
    assert "Traceback" not in result.stdout
