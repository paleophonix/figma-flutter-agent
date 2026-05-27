"""Tests for layout_common helpers."""

from figma_flutter_agent.generator.layout_common import escape_dart_string


def test_escape_dart_string_handles_newlines() -> None:
    assert escape_dart_string("Everyday is best, but we recommend picking\nat least five.") == (
        "Everyday is best, but we recommend picking\\nat least five."
    )


def test_escape_dart_string_handles_quotes_and_backslashes() -> None:
    assert escape_dart_string("it's a \\path") == "it\\'s a \\\\path"
