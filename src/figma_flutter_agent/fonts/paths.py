"""Canonical Flutter font asset paths under ``assets/fonts/``."""

from __future__ import annotations

from pathlib import Path

FONTS_ASSET_DIR = Path("assets/fonts")
FONTS_ASSET_PREFIX = "assets/fonts"


def project_fonts_dir(project_dir: Path) -> Path:
    """Return ``<project>/assets/fonts``."""
    return project_dir / FONTS_ASSET_DIR


def pubspec_font_asset_path(asset_name: str) -> str:
    """Return a ``pubspec.yaml`` ``flutter.fonts`` asset path."""
    return f"{FONTS_ASSET_PREFIX}/{asset_name}"


def is_valid_font_bytes(data: bytes) -> bool:
    """Return True when ``data`` looks like a TTF/OTF/WOFF font file."""
    if len(data) < 256:
        return False
    signature = data[:4]
    return signature in (
        b"\x00\x01\x00\x00",
        b"OTTO",
        b"true",
        b"wOFF",
        b"wOF2",
    )
