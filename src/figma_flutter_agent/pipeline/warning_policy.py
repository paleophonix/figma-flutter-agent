"""Classify pipeline messages: expected optional-path noise vs actionable warnings."""

from __future__ import annotations

from typing import Any, Literal

from loguru import logger

from figma_flutter_agent.config import Settings

StyleMetadataSource = Literal["rest_synthesis", "dev_mode_inspect", "hybrid"]


def quiet_expected_warnings(settings: Settings) -> bool:
    """When true, demote expected optional-path noise to info/debug."""
    return settings.agent.runtime.quiet_expected_warnings


def is_quiet_expected(*, settings: Settings | None = None) -> bool:
    """Return quiet mode from explicit settings or the loaded default config."""
    if settings is not None:
        return quiet_expected_warnings(settings)
    from figma_flutter_agent.config import load_settings

    return quiet_expected_warnings(load_settings(config_path=None))


def log_recoverable(
    message: str,
    /,
    *args: object,
    settings: Settings | None = None,
    **kwargs: object,
) -> None:
    """Log a successful fallback path at info when quiet mode is enabled."""
    log_fn = logger.info if is_quiet_expected(settings=settings) else logger.warning
    log_fn(message, *args, **kwargs)


def log_recoverable_debug(
    message: str,
    /,
    *args: object,
    settings: Settings | None = None,
    **kwargs: object,
) -> None:
    """Log chatty recoverable telemetry at debug when quiet mode is enabled."""
    log_fn = logger.debug if is_quiet_expected(settings=settings) else logger.warning
    log_fn(message, *args, **kwargs)


def log_dev_mode_css_load_failure(
    log: Any,
    *,
    settings: Settings,
    style_source: StyleMetadataSource,
    exc: Exception,
) -> None:
    """Log missing CSS dump at debug/info unless dev_mode_inspect requires the file."""
    if quiet_expected_warnings(settings):
        log.info(
            "Dev Mode CSS dump not loaded (optional for {}): {}",
            style_source,
            exc,
        )
        return
    if style_source == "dev_mode_inspect":
        log.warning("Dev Mode CSS dump could not be loaded — continuing without it: {}", exc)
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


_ACTIONABLE_WARNING_PREFIXES = (
    "Asset export",
    "Render-boundary",
)


def is_actionable_user_warning(message: str) -> bool:
    """Return True when a pipeline warning must not be demoted to info."""
    stripped = message.strip()
    return any(stripped.startswith(prefix) for prefix in _ACTIONABLE_WARNING_PREFIXES)


def emit_user_warnings(warnings: list[str], *, settings: Settings) -> None:
    """Log pipeline user warnings at the configured severity."""
    from loguru import logger

    quiet = quiet_expected_warnings(settings)
    for message in warnings:
        if not message.strip():
            continue
        if is_actionable_user_warning(message):
            logger.warning("{}", message)
        elif quiet:
            logger.info("{}", message)
        else:
            logger.warning("{}", message)
