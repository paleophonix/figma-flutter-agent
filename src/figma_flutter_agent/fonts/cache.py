"""Persistent SHA-256 disk cache for downloaded font binaries."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from loguru import logger

_DEFAULT_CACHE_DIR = Path.home() / ".config" / "figma-flutter-agent" / "cache" / "fonts"


def font_cache_dir() -> Path:
    """Return the directory used for cached font downloads.

    Returns:
        Cache directory path from ``FIGMA_FLUTTER_FONT_CACHE_DIR`` or the default
        user config location.
    """
    override = os.getenv("FIGMA_FLUTTER_FONT_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _DEFAULT_CACHE_DIR


def cache_path_for_url(url: str) -> Path:
    """Build a stable cache file path for a download URL.

    Args:
        url: Remote font file URL.

    Returns:
        Absolute cache file path keyed by SHA-256 of ``url``.
    """
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return font_cache_dir() / f"{digest}.bin"


def read_cached_font(url: str) -> bytes | None:
    """Read cached font bytes for ``url`` when present.

    Args:
        url: Remote font file URL.

    Returns:
        Cached bytes, or ``None`` when no cache entry exists.
    """
    path = cache_path_for_url(url)
    if not path.is_file():
        return None
    return path.read_bytes()


def write_cached_font(url: str, data: bytes) -> Path:
    """Persist downloaded font bytes into the cache.

    Args:
        url: Remote font file URL.
        data: Downloaded font binary.

    Returns:
        Path to the written cache file.
    """
    path = cache_path_for_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.debug("Cached font download at {}", path.as_posix())
    return path


def clear_font_cache() -> None:
    """Remove all cached font files (for tests)."""
    cache_dir = font_cache_dir()
    if not cache_dir.is_dir():
        return
    for path in cache_dir.glob("*.bin"):
        path.unlink(missing_ok=True)
