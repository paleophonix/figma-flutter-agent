"""Tests for sanitized Figma API errors."""

from figma_flutter_agent.errors import (
    FigmaApiError,
    LlmError,
    format_error_for_log,
    sanitize_api_message,
)


def test_sanitize_api_message_truncates_and_redacts_secrets() -> None:
    body = "figd_secret1234567890 " + ("x" * 300)
    sanitized = sanitize_api_message(body)

    assert "figd_" not in sanitized
    assert "***" in sanitized
    assert len(sanitized) <= 250


def test_figma_api_error_applies_sanitization() -> None:
    error = FigmaApiError('{"err":"invalid","token":"figd_abc123xyz"}', status_code=403)

    assert "figd_" not in str(error)
    assert error.status_code == 403


def test_format_error_for_log_includes_type_status_message_and_cause() -> None:
    root = TimeoutError("TLS handshake timed out")
    error = LlmError("OpenRouter request timed out (model=x)", status_code=None)
    error.__cause__ = root

    formatted = format_error_for_log(error)

    assert "LlmError" in formatted
    assert "OpenRouter request timed out" in formatted
    assert "cause=TimeoutError" in formatted
    assert "TLS handshake" in formatted


def test_format_error_for_log_includes_figma_http_body() -> None:
    error = FigmaApiError('{"status":403,"err":"Not authorized"}', status_code=403)
    formatted = format_error_for_log(error)

    assert "FigmaApiError" in formatted
    assert "status=403" in formatted
    assert "Not authorized" in formatted
