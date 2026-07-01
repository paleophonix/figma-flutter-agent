"""Custom exceptions for the Figma Flutter agent."""

from __future__ import annotations

from figma_flutter_agent.redaction import redact_secrets

_API_BODY_MAX_LEN = 240


def sanitize_api_message(message: str, *, max_len: int = _API_BODY_MAX_LEN) -> str:
    """Truncate and redact secrets from Figma HTTP error bodies."""
    trimmed = message.strip()
    if len(trimmed) > max_len:
        trimmed = f"{trimmed[:max_len]}..."
    return redact_secrets(trimmed)


def format_error_for_log(exc: BaseException, *, max_message_len: int = 400) -> str:
    """Build a single log line with exception type, HTTP status, message, and cause.

    Args:
        exc: Caught exception to summarize.
        max_message_len: Maximum characters for the primary message segment.

    Returns:
        Redacted, human-readable error summary for Loguru or CLI output.
    """
    headline = type(exc).__name__
    status_code = getattr(exc, "status_code", None)
    message = str(exc).strip()
    if message:
        if isinstance(exc, FigmaApiError):
            message = sanitize_api_message(message, max_len=max_message_len)
        else:
            message = redact_secrets(message)
            if len(message) > max_message_len:
                message = f"{message[:max_message_len]}..."

    segments = [headline]
    if status_code is not None:
        segments.append(f"status={status_code}")
    if message:
        segments.append(message)
    elif status_code is not None:
        segments.append("(empty response body)")

    cause = exc.__cause__
    if cause is not None:
        cause_message = redact_secrets(str(cause).strip())
        if cause_message:
            if len(cause_message) > 160:
                cause_message = f"{cause_message[:160]}..."
            segments.append(f"cause={type(cause).__name__}: {cause_message}")

    return " | ".join(segments)


class FigmaFlutterError(Exception):
    """Base error for the Figma Flutter agent."""


class FigmaUrlError(FigmaFlutterError):
    """Raised when a Figma URL cannot be parsed."""


class FigmaApiError(FigmaFlutterError):
    """Raised when the Figma REST API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(sanitize_api_message(message))
        self.status_code = status_code


class FlutterProjectError(FigmaFlutterError):
    """Raised when the target Flutter project path is invalid."""


class FlutterPreviewLaunchError(FlutterProjectError):
    """Raised when ``flutter run`` preview launch fails after codegen succeeded."""


class ParseError(FigmaFlutterError):
    """Raised when Figma JSON cannot be converted to a clean design tree."""


class PipelineError(FigmaFlutterError):
    """Raised when an internal pipeline stage invariant is violated."""


class LlmError(FigmaFlutterError):
    """Raised when LLM generation or validation fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LlmRepairStalledError(LlmError):
    """Raised when analyze repair makes no progress on syntax errors."""


class GenerationError(FigmaFlutterError):
    """Raised when writing generated files fails."""


class PlannedDartGraphError(GenerationError):
    """Raised when planned Dart files reference missing ``lib/widgets`` targets."""


class SnapshotConflictError(FigmaFlutterError):
    """Raised when incremental sync snapshot was modified by another process."""


class FastPreviewUnavailableError(FigmaFlutterError):
    """Raised when browser preview capture backend is missing or misconfigured."""
