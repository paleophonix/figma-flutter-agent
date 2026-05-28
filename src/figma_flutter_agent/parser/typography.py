"""Figma text style normalization for Flutter typography."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_micro_style

_WEIGHT_HINTS: tuple[tuple[str, str], ...] = (
    ("thin", "w100"),
    ("extralight", "w200"),
    ("ultralight", "w200"),
    ("light", "w300"),
    ("regular", "w400"),
    ("normal", "w400"),
    ("medium", "w500"),
    ("semibold", "w600"),
    ("demibold", "w600"),
    ("bold", "w700"),
    ("extrabold", "w800"),
    ("heavy", "w800"),
    ("black", "w900"),
)


def _weight_from_names(*names: str | None) -> str | None:
    """Infer Flutter weight token from Figma font face names."""
    combined = " ".join(name for name in names if name).lower()
    normalized = combined.replace("-", "").replace("_", "").replace(" ", "")
    for hint, weight in _WEIGHT_HINTS:
        if hint in normalized:
            return weight
    return None


def resolve_font_weight(text_style: dict[str, Any]) -> str | None:
    """Resolve Flutter ``FontWeight`` token from a Figma ``style`` object.

    Figma often reports ``fontWeight: 400`` while ``fontPostScriptName`` is
    ``HelveticaNeueMedium``. Prefer the named face over the numeric field.
    """
    from_name = _weight_from_names(
        text_style.get("fontPostScriptName"),
        text_style.get("fontStyle"),
    )
    if from_name is not None:
        return from_name
    weight = text_style.get("fontWeight")
    if weight is not None:
        return f"w{int(weight)}"
    return None


def resolve_font_family(text_style: dict[str, Any]) -> str | None:
    """Map a Figma ``fontFamily`` value to a Flutter ``fontFamily`` string."""
    from figma_flutter_agent.fonts.sources import FIGMA_FAMILY_ALIASES

    raw = text_style.get("fontFamily")
    if raw is None:
        return None
    trimmed = str(raw).strip()
    if not trimmed:
        return None
    key = trimmed.lower().replace(" ", "")
    alias = FIGMA_FAMILY_ALIASES.get(key)
    if alias is not None:
        return alias
    alias = FIGMA_FAMILY_ALIASES.get(trimmed.lower())
    if alias is not None:
        return alias
    return trimmed


def resolve_font_style(text_style: dict[str, Any]) -> str | None:
    """Return ``italic`` when the Figma style describes an italic/oblique face."""
    for key in ("fontStyle", "fontPostScriptName"):
        value = str(text_style.get(key) or "").lower()
        if "italic" in value or "oblique" in value:
            return "italic"
    return None


def resolve_letter_spacing(text_style: dict[str, Any], *, font_size: float | None) -> float | None:
    """Normalize Figma tracking to Flutter ``letterSpacing`` logical pixels."""
    if text_style.get("letterSpacing") is not None:
        return round_micro_style(float(text_style["letterSpacing"]))
    percent = text_style.get("letterSpacingPercent")
    if percent is not None and font_size is not None:
        return round_micro_style(float(percent) / 100.0 * float(font_size))
    return None
