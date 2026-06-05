"""Read typographic metrics from bundled font binaries."""

from __future__ import annotations

import re
import struct
from pathlib import Path

from figma_flutter_agent.fonts.paths import is_valid_font_bytes, project_fonts_dir

_TTF_SIGNATURES = frozenset({b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"})
_TYPICAL_ASCENDER_RATIO = 0.88
_FLUTTER_BASELINE_CALIBRATION = 0.72 / _TYPICAL_ASCENDER_RATIO


def _family_asset_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", family.strip().lower()).strip("_") or "font"


def _table_directory(data: bytes) -> dict[str, tuple[int, int]]:
    if len(data) < 12 or data[:4] not in _TTF_SIGNATURES:
        return {}
    num_tables = struct.unpack_from(">H", data, 4)[0]
    tables: dict[str, tuple[int, int]] = {}
    for index in range(num_tables):
        record = 12 + index * 16
        if record + 16 > len(data):
            break
        tag = data[record : record + 4].decode("ascii", errors="ignore")
        offset = struct.unpack_from(">I", data, record + 8)[0]
        length = struct.unpack_from(">I", data, record + 12)[0]
        if offset + length <= len(data):
            tables[tag] = (offset, length)
    return tables


def _units_per_em(data: bytes, tables: dict[str, tuple[int, int]]) -> int | None:
    head = tables.get("head")
    if head is None:
        return None
    offset, length = head
    if length < 20:
        return None
    return int(struct.unpack_from(">H", data, offset + 18)[0])


def _os2_typo_ascender(data: bytes, tables: dict[str, tuple[int, int]]) -> int | None:
    os2 = tables.get("OS/2")
    if os2 is None:
        return None
    offset, length = os2
    if length < 70:
        return None
    return int(struct.unpack_from(">h", data, offset + 68)[0])


def _hhea_ascender(data: bytes, tables: dict[str, tuple[int, int]]) -> int | None:
    hhea = tables.get("hhea")
    if hhea is None:
        return None
    offset, length = hhea
    if length < 6:
        return None
    return int(struct.unpack_from(">h", data, offset + 4)[0])


def typographic_baseline_ratio(font_bytes: bytes) -> float | None:
    """Map a font binary to the planner baseline ratio scale.

    Args:
        font_bytes: Raw TTF/OTF payload.

    Returns:
        Calibrated baseline ratio, or ``None`` when tables are unreadable.
    """
    if not is_valid_font_bytes(font_bytes):
        return None
    tables = _table_directory(font_bytes)
    units = _units_per_em(font_bytes, tables)
    if units is None or units <= 0:
        return None
    ascender = _os2_typo_ascender(font_bytes, tables)
    if ascender is None or ascender <= 0:
        ascender = _hhea_ascender(font_bytes, tables)
    if ascender is None or ascender <= 0:
        return None
    return (ascender / units) * _FLUTTER_BASELINE_CALIBRATION


def project_font_paths_for_family(project_dir: Path, family: str) -> list[Path]:
    """Return bundled font files that match a pubspec/Figma family slug."""
    fonts_dir = project_fonts_dir(project_dir)
    if not fonts_dir.is_dir():
        return []
    slug = _family_asset_slug(family)
    paths: list[Path] = []
    for pattern in (f"{slug}_*.ttf", f"{slug}_*.otf", f"{slug}.ttf", f"{slug}.otf"):
        paths.extend(sorted(fonts_dir.glob(pattern)))
    return paths


def baseline_ratio_from_project_fonts(project_dir: Path, family: str) -> float | None:
    """Resolve a baseline ratio from ``assets/fonts`` when present."""
    for path in project_font_paths_for_family(project_dir, family):
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        ratio = typographic_baseline_ratio(payload)
        if ratio is not None:
            return ratio
    return None
