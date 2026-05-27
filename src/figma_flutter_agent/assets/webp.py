"""WebP export prerequisites."""

from __future__ import annotations


def webp_conversion_available() -> bool:
    """Return True when Pillow can convert PNG assets to WebP."""
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False
