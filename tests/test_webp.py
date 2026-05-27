"""Tests for WebP export prerequisites."""

from figma_flutter_agent.assets.webp import webp_conversion_available


def test_webp_conversion_available_when_pillow_installed() -> None:
    assert webp_conversion_available() is True
