"""Canonical Flutter font asset paths under ``assets/fonts/``."""

from __future__ import annotations

from pathlib import Path

FONTS_ASSET_DIR = Path("assets/fonts")
FONTS_ASSET_PREFIX = "assets/fonts"
MIN_FONT_BUNDLE_BYTES = 15000
_MAX_FONT_TABLE_COUNT = 64


def project_fonts_dir(project_dir: Path) -> Path:
    """Return ``<project>/assets/fonts``."""
    return project_dir / FONTS_ASSET_DIR


def pubspec_font_asset_path(asset_name: str) -> str:
    """Return a ``pubspec.yaml`` ``flutter.fonts`` asset path."""
    return f"{FONTS_ASSET_PREFIX}/{asset_name}"


def _font_table_directory_plausible(data: bytes) -> bool:
    """Return True when a TrueType/OpenType table directory looks structurally valid."""
    if len(data) < 12:
        return False
    num_tables = int.from_bytes(data[4:6], "big")
    if num_tables < 1 or num_tables > _MAX_FONT_TABLE_COUNT:
        return False
    directory_end = 12 + num_tables * 16
    if len(data) < directory_end:
        return False
    for index in range(num_tables):
        record = 12 + index * 16
        table_offset = int.from_bytes(data[record + 8 : record + 12], "big")
        table_length = int.from_bytes(data[record + 12 : record + 16], "big")
        if table_length > 0 and table_offset + table_length <= len(data):
            return True
    return False


def is_valid_font_bytes(data: bytes) -> bool:
    """Return True when ``data`` looks like a loadable TTF/OTF/WOFF font file."""
    if len(data) < MIN_FONT_BUNDLE_BYTES:
        return False
    signature = data[:4]
    if signature in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
        return _font_table_directory_plausible(data)
    return signature in (b"wOFF", b"wOF2")
