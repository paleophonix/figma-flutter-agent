"""Tests for Loguru logging setup."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent import logging_setup


def test_configure_logging_preserves_braces_in_messages(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "figma_flutter_agent.log"
    monkeypatch.setattr(logging_setup, "LOG_FILE", log_file)

    logging_setup.configure_logging(verbose=False)
    logger.warning("{}", "Manual edits in lib/theme/app_layout.dart: class AppBreakpoints {")

    content = log_file.read_text(encoding="utf-8")
    assert "class AppBreakpoints {" in content
