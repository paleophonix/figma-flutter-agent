"""Tests for Loguru logging setup."""

from __future__ import annotations

import sys

from loguru import logger

from figma_flutter_agent import logging_setup


def test_configure_logging_preserves_braces_in_messages(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "figma_flutter_agent.log"
    monkeypatch.setattr(logging_setup, "LOG_FILE", log_file)

    from figma_flutter_agent.config import Settings

    logging_setup.configure_logging(
        verbose=False,
        settings=Settings.model_construct(loki_url=""),
    )
    logger.warning("{}", "Manual edits in lib/theme/app_layout.dart: class AppBreakpoints {")
    logger.complete()

    content = log_file.read_text(encoding="utf-8")
    assert "class AppBreakpoints {" in content


def test_file_log_rotation_disabled_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert logging_setup.file_log_rotation() is None
    assert logging_setup.file_log_retention() is None


def test_file_log_rotation_enabled_on_posix(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert logging_setup.file_log_rotation() == "10 MB"
    assert logging_setup.file_log_retention() == "7 days"


def test_configure_logging_attaches_loki_when_url_set(monkeypatch) -> None:
    from pydantic import SecretStr

    from figma_flutter_agent.config import Settings

    settings = Settings.model_construct(
        loki_url="https://logs.example.com",
        loki_api_key=SecretStr("glc_test"),
    )
    calls: list[dict[str, object]] = []

    def _attach(**kwargs: object) -> object:
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(logging_setup, "attach_loki_sink", _attach)
    logging_setup.configure_logging(verbose=False, settings=settings)
    assert calls == [{"settings": settings, "level": "INFO"}]
