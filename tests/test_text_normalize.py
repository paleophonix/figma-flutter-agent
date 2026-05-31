"""Tests for Figma TEXT character normalization."""

from figma_flutter_agent.parser.text_normalize import normalize_figma_characters


def test_normalize_figma_characters_collapses_spaces_before_newline() -> None:
    raw = "Thousand of people are usign silent moon  \nfor smalls meditation "
    assert normalize_figma_characters(raw) == (
        "Thousand of people are usign silent moon\nfor smalls meditation"
    )
