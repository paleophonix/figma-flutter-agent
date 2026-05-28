"""Match design font faces to files in ``assets/fonts/`` (exact basename only)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from figma_flutter_agent.fonts.googlefonts import weight_token_to_int
from figma_flutter_agent.fonts.paths import (
    is_valid_font_bytes,
    project_fonts_dir,
)
from figma_flutter_agent.schemas import FontFaceRequirement

_FONT_EXTENSIONS = frozenset({".ttf", ".otf", ".woff", ".woff2"})
LEGACY_FONTS_DIR = Path("fonts")
_LEGACY_FONTS_DIR = LEGACY_FONTS_DIR
FontMatchKind = Literal["exact", "analog", "missing"]


@dataclass(frozen=True)
class LocalFontMatch:
    """How a design face maps to a file in ``assets/fonts/``."""

    kind: FontMatchKind
    path: Path | None
    expected_basename: str


def _asset_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", family.strip().lower()).strip("_") or "font"


def expected_asset_name(
    pubspec_family: str,
    weight: int,
    style: str | None,
    *,
    ext: str,
) -> str:
    """Return the canonical bundled font filename for a pubspec family."""
    style_suffix = f"_{style}" if style else ""
    return f"{_asset_slug(pubspec_family)}_{weight}{style_suffix}{ext}"


def expected_analog_asset_name(
    pubspec_family: str,
    weight: int,
    style: str | None,
    *,
    ext: str,
) -> str:
    """Return the bundled substitute filename (``*_analog.ttf`` / ``.otf``)."""
    style_suffix = f"_{style}" if style else ""
    return f"{_asset_slug(pubspec_family)}_{weight}{style_suffix}_analog{ext}"


def _migrate_legacy_fonts_dir(project_dir: Path, target: Path) -> None:
    """Copy fonts from deprecated project-root ``fonts/`` into ``assets/fonts/``."""
    legacy = project_dir / _LEGACY_FONTS_DIR
    if not legacy.is_dir():
        return
    for path in legacy.iterdir():
        if not path.is_file() or path.suffix.lower() not in _FONT_EXTENSIONS:
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if not is_valid_font_bytes(payload):
            continue
        destination = target / path.name
        if destination.is_file():
            continue
        shutil.copy2(path, destination)


def legacy_project_fonts_dir(project_dir: Path) -> Path:
    """Deprecated project-root ``fonts/`` (use ``assets/fonts/`` only)."""
    return project_dir / LEGACY_FONTS_DIR


def list_legacy_font_basenames(project_dir: Path) -> tuple[str, ...]:
    """Return font basenames in deprecated ``fonts/`` when that directory exists."""
    legacy = legacy_project_fonts_dir(project_dir)
    if not legacy.is_dir():
        return ()
    names: list[str] = []
    for path in sorted(legacy.iterdir()):
        if path.is_file() and path.suffix.lower() in _FONT_EXTENSIONS:
            names.append(path.name)
    return tuple(names)


def ensure_project_fonts_dir(project_dir: Path) -> Path:
    """Create ``assets/fonts/`` when missing and return its path."""
    fonts_dir = project_fonts_dir(project_dir)
    fonts_dir.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_fonts_dir(project_dir, fonts_dir)
    return fonts_dir


def _is_usable_font_file(path: Path) -> bool:
    try:
        return is_valid_font_bytes(path.read_bytes())
    except OSError:
        return False


def _family_for_name(face: FontFaceRequirement, pubspec_family: str | None) -> str:
    return pubspec_family or face.figma_family.strip()


def _style_for_face(face: FontFaceRequirement) -> str | None:
    return face.font_style if face.font_style == "italic" else None


def _expected_original_basenames(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None,
) -> tuple[str, str]:
    family_for_name = _family_for_name(face, pubspec_family)
    weight = weight_token_to_int(face.font_weight)
    style = _style_for_face(face)
    ttf = expected_asset_name(family_for_name, weight, style, ext=".ttf")
    otf = expected_asset_name(family_for_name, weight, style, ext=".otf")
    return ttf, otf


def _expected_analog_basenames(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None,
) -> tuple[str, str]:
    family_for_name = _family_for_name(face, pubspec_family)
    weight = weight_token_to_int(face.font_weight)
    style = _style_for_face(face)
    ttf = expected_analog_asset_name(family_for_name, weight, style, ext=".ttf")
    otf = expected_analog_asset_name(family_for_name, weight, style, ext=".otf")
    return ttf, otf


def _find_exact_font_file(
    fonts_dir: Path,
    *,
    expected_ttf: str,
    expected_otf: str,
) -> Path | None:
    for name in (expected_ttf, expected_otf):
        path = fonts_dir / name
        if path.is_file() and _is_usable_font_file(path):
            return path
    return None


def _find_analog_font_file(
    fonts_dir: Path,
    *,
    expected_ttf: str,
    expected_otf: str,
) -> Path | None:
    for name in (expected_ttf, expected_otf):
        path = fonts_dir / name
        if path.is_file() and _is_usable_font_file(path):
            return path
    return None


def find_local_original_font_file(
    face: FontFaceRequirement,
    project_dir: Path,
    *,
    pubspec_family: str | None = None,
) -> Path | None:
    """Find the original (non-analog) font file when the exact basename exists."""
    fonts_dir = ensure_project_fonts_dir(project_dir)
    expected_ttf, expected_otf = _expected_original_basenames(face, pubspec_family=pubspec_family)
    return _find_exact_font_file(fonts_dir, expected_ttf=expected_ttf, expected_otf=expected_otf)


def find_local_analog_font_file(
    face: FontFaceRequirement,
    project_dir: Path,
    *,
    pubspec_family: str | None = None,
) -> Path | None:
    """Find a previously downloaded ``*_analog`` substitute on disk."""
    fonts_dir = ensure_project_fonts_dir(project_dir)
    expected_ttf, expected_otf = _expected_analog_basenames(face, pubspec_family=pubspec_family)
    return _find_analog_font_file(fonts_dir, expected_ttf=expected_ttf, expected_otf=expected_otf)


def classify_local_font_match(
    face: FontFaceRequirement,
    project_dir: Path,
    *,
    pubspec_family: str | None = None,
) -> LocalFontMatch:
    """Return exact, on-disk analog, or missing."""
    fonts_dir = ensure_project_fonts_dir(project_dir)
    orig_ttf, orig_otf = _expected_original_basenames(face, pubspec_family=pubspec_family)
    analog_ttf, analog_otf = _expected_analog_basenames(face, pubspec_family=pubspec_family)
    expected_label = (
        f"{orig_ttf} or {orig_otf} (original); {analog_ttf} or {analog_otf} (substitute)"
    )

    exact = _find_exact_font_file(fonts_dir, expected_ttf=orig_ttf, expected_otf=orig_otf)
    if exact is not None:
        return LocalFontMatch(kind="exact", path=exact, expected_basename=expected_label)

    analog = _find_analog_font_file(
        fonts_dir,
        expected_ttf=analog_ttf,
        expected_otf=analog_otf,
    )
    if analog is not None:
        return LocalFontMatch(kind="analog", path=analog, expected_basename=expected_label)

    return LocalFontMatch(kind="missing", path=None, expected_basename=expected_label)


def find_local_font_file(
    face: FontFaceRequirement,
    project_dir: Path,
    *,
    pubspec_family: str | None = None,
) -> Path | None:
    """Find original first, then an on-disk ``*_analog`` file."""
    original = find_local_original_font_file(face, project_dir, pubspec_family=pubspec_family)
    if original is not None:
        return original
    return find_local_analog_font_file(face, project_dir, pubspec_family=pubspec_family)
