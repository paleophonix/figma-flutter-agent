"""Tests for ``figma-flutter defects`` CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from figma_flutter_agent.cli import app


def test_defects_validate_success() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["defects", "validate"])
    assert result.exit_code == 0, result.stdout
    assert "valid" in result.stdout
