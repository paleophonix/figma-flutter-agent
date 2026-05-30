"""WCAG-readable foreground on arbitrary fills."""

from __future__ import annotations

from figma_flutter_agent.parser.accessibility import readable_foreground_hex


def test_readable_foreground_picks_best_when_preferred_fails_wcag() -> None:
    assert readable_foreground_hex("0xFF1A1A2E", "0xFF333333") == "0xFFFFFFFF"


def test_readable_foreground_keeps_preferred_when_contrast_passes() -> None:
    assert readable_foreground_hex("0xFF1A1A2E", "0xFFFFFFFF") == "0xFFFFFFFF"
