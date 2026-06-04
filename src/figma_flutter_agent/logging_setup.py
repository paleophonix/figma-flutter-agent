"""Loguru configuration for the CLI."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.redaction import redact_secrets

_LOGURU_FIELD_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_.]*\}")

LOG_FILE = Path("logs/figma_flutter_agent.log")

_STDERR_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>\n"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}\n"
)


def _logging_patcher(record: dict[str, Any]) -> None:
    """Escape Loguru field placeholders only (``{name}``), not Dart ``{`` in log text."""
    message = redact_secrets(str(record["message"]))

    def _escape_field(match: re.Match[str]) -> str:
        return match.group(0).replace("{", "{{").replace("}", "}}")

    record["message"] = _LOGURU_FIELD_RE.sub(_escape_field, message)


def configure_logging(*, verbose: bool = False) -> None:
    """Configure global Loguru logging for CLI runs.

    Args:
        verbose: When True, emit DEBUG-level logs; otherwise INFO.
    """
    logger.remove()
    logger.configure(patcher=_logging_patcher)
    level = "DEBUG" if verbose else "INFO"

    logger.add(
        sys.stderr,
        level=level,
        format=_STDERR_FORMAT,
        colorize=True,
    )

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_FILE,
        level=level,
        format=_FILE_FORMAT,
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
        colorize=False,
        enqueue=True,
        catch=True,
    )
