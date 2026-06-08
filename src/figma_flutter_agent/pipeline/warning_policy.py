"""Classify pipeline messages: expected optional-path noise vs actionable warnings."""

from __future__ import annotations

from typing import Any, Literal

from figma_flutter_agent.config import Settings

StyleMetadataSource = Literal["rest_synthesis", "dev_mode_inspect", "hybrid"]


def quiet_expected_warnings(settings: Settings) -> bool:
    """When true, demote expected optional-path noise to info/debug."""
    return settings.agent.runtime.quiet_expected_warnings


def log_dev_mode_css_load_failure(
    log: Any,
    *,
    settings: Settings,
    style_source: StyleMetadataSource,
    exc: Exception,
) -> None:
    """Log missing CSS dump at debug/info unless dev_mode_inspect requires the file."""
    if style_source == "dev_mode_inspect":
        log.warning("Dev Mode CSS dump could not be loaded — continuing without it: {}", exc)
        return
    if quiet_expected_warnings(settings):
        log.info(
            "Dev Mode CSS dump not loaded (optional for {}): {}",
            style_source,
            exc,
        )
        return
    log.warning("Dev Mode CSS dump could not be loaded — continuing without it: {}", exc)


def cached_ir_user_warning(message: str, *, settings: Settings) -> str | None:
    """Return user-facing warning text, or None when cached IR is expected noise."""
    if quiet_expected_warnings(settings):
        return None
    return message


def skip_delegates_to_layout_warning(*, settings: Settings, use_cached_ir: bool) -> bool:
    """Skip 'screen delegates to Layout' when offline IR noise is expected."""
    if not quiet_expected_warnings(settings):
        return False
    return use_cached_ir


def emit_user_warnings(warnings: list[str], *, settings: Settings) -> None:
    """Log pipeline user warnings at the configured severity."""
    from loguru import logger

    log_fn = logger.info if quiet_expected_warnings(settings) else logger.warning
    for message in warnings:
        if message.strip():
            log_fn("{}", message)
