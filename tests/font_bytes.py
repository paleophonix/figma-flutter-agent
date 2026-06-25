"""Shared font byte fixtures for tests."""

from __future__ import annotations

from figma_flutter_agent.fonts.paths import MIN_FONT_BUNDLE_BYTES


def minimal_ttf_payload() -> bytes:
    """Return a structurally plausible TTF large enough for bundle validation."""
    num_tables = 4
    header = bytearray(b"\x00\x01\x00\x00")
    header += num_tables.to_bytes(2, "big")
    header += b"\x00\x00\x00\x00\x00\x00"
    header += b"head"
    header += b"\x00\x00\x00\x00"
    header += (76).to_bytes(4, "big")
    header += (128).to_bytes(4, "big")
    directory_end = 12 + num_tables * 16
    if len(header) < directory_end:
        header.extend(b"\x00" * (directory_end - len(header)))
    if len(header) < MIN_FONT_BUNDLE_BYTES:
        header.extend(b"\x00" * (MIN_FONT_BUNDLE_BYTES - len(header)))
    return bytes(header)
