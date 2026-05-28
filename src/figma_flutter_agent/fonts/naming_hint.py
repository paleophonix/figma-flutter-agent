"""Expected bundled font filenames and rename hints for warnings."""

from __future__ import annotations

from figma_flutter_agent.fonts.googlefonts import weight_token_to_int
from figma_flutter_agent.fonts.local import expected_analog_asset_name, expected_asset_name
from figma_flutter_agent.schemas import FontFaceRequirement

RENAME_IF_PRESENT_HINT = (
    "Original: exact name under need. Substitute downloads are saved as *_analog.ttf "
    "(or .otf) — warnings still apply when an analog is used."
)


def format_expected_font_filenames(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None = None,
) -> str:
    """Return expected original ``assets/fonts/`` basenames."""
    family = (pubspec_family or face.figma_family).strip()
    weight = weight_token_to_int(face.font_weight)
    style = face.font_style if face.font_style == "italic" else None
    candidates = [
        expected_asset_name(family, weight, style, ext=ext)
        for ext in (".ttf", ".otf")
    ]
    return " or ".join(candidates)


def format_expected_analog_filenames(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None = None,
) -> str:
    """Return expected ``*_analog`` basenames for a downloaded substitute."""
    family = (pubspec_family or face.figma_family).strip()
    weight = weight_token_to_int(face.font_weight)
    style = face.font_style if face.font_style == "italic" else None
    candidates = [
        expected_analog_asset_name(family, weight, style, ext=ext)
        for ext in (".ttf", ".otf")
    ]
    return " or ".join(candidates)


def missing_face_hint(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None = None,
) -> str:
    """Human-readable missing-face line with expected original and analog names."""
    style = f" {face.font_style}" if face.font_style else ""
    label = f"{face.figma_family} ({face.font_weight}{style})"
    original = format_expected_font_filenames(face, pubspec_family=pubspec_family)
    analog = format_expected_analog_filenames(face, pubspec_family=pubspec_family)
    return f"{label} → original: {original}; substitute: {analog}"


def append_rename_hint(
    message: str,
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None = None,
) -> str:
    """Append guidance to place the original font file."""
    expected = format_expected_font_filenames(face, pubspec_family=pubspec_family)
    return (
        f"{message} Place the original font in assets/fonts/ as exactly: {expected}."
    )


def format_substitute_offer(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None,
    asset_name: str,
    source_label: str,
) -> str:
    """Hint when a substitute is available but auto-download is disabled."""
    style = f"{' ' + face.font_style}" if face.font_style else ""
    original = format_expected_font_filenames(face, pubspec_family=pubspec_family)
    return (
        f"Font '{face.figma_family}' ({face.font_weight}{style}): not in assets/fonts/ ({original}). "
        f"Substitute available ({source_label}) → assets/fonts/{asset_name}. "
        "Set fonts.download_fonts: true to download, or add the original file."
    )


def analog_usage_warning(
    face: FontFaceRequirement,
    *,
    pubspec_family: str | None,
    substitute_label: str,
    saved_as: str | None = None,
) -> str:
    """Warning when a run uses a substitute (on disk or freshly downloaded)."""
    style = f"{' ' + face.font_style}" if face.font_style else ""
    original = format_expected_font_filenames(face, pubspec_family=pubspec_family)
    analog_names = format_expected_analog_filenames(face, pubspec_family=pubspec_family)
    saved_clause = f" File: assets/fonts/{saved_as}." if saved_as else ""
    return (
        f"Font '{face.figma_family}' ({face.font_weight}{style}): using analog substitute "
        f"({substitute_label}); original not in assets/fonts/ ({original}).{saved_clause} "
        f"Substitute files use the _analog suffix (e.g. {analog_names})."
    )
