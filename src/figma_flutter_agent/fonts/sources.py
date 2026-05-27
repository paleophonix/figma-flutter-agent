"""Bundled font source definitions (Figma family -> downloadable files)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.fonts.registry import load_font_registry, normalize_figma_family_key


@dataclass(frozen=True)
class BundledWeightFile:
    """One font file mapped to a Flutter ``FontWeight`` value."""

    archive_name: str
    asset_name: str
    weight: int
    style: str | None = None
    download_url: str | None = None


@dataclass(frozen=True)
class BundledFontPackage:
    """Downloadable font package for a pubspec ``family`` name."""

    pubspec_family: str
    zip_url: str | None
    weight_files: dict[str, BundledWeightFile]


def _registry() -> object:
    return load_font_registry()


def normalize_figma_family(name: str) -> str:
    """Normalize a Figma ``fontFamily`` string for alias lookup."""
    registry = _registry()
    normalized_key = normalize_figma_family_key(name)
    entry = registry.lookup(name)
    if entry is not None:
        return entry.pubspec_family
    aliases = registry.figma_to_pubspec_aliases()
    alias = aliases.get(normalized_key) or aliases.get(normalized_key.replace(" ", ""))
    return alias if alias is not None else name.strip()


def bundled_package_for_family(pubspec_family: str) -> BundledFontPackage | None:
    """Return a proprietary substitute package when ``pubspec_family`` is supported."""
    registry = _registry()
    entry = registry.pubspec_index.get(pubspec_family.strip().lower())
    if entry is None or entry.strategy != "bundled" or not entry.bundled_weights:
        return None
    profile = registry.profiles.get(entry.profile_id)
    weight_files: dict[str, BundledWeightFile] = {}
    for token, spec in entry.bundled_weights.items():
        style_key = weight_file_key(token, spec.style)
        pubspec_weight = spec.weight
        if profile is not None:
            pubspec_weight = profile.effective_pubspec_weight(token)
        weight_files[style_key] = BundledWeightFile(
            archive_name=Path(spec.url).name,
            asset_name=spec.asset_name,
            weight=pubspec_weight,
            style=spec.style,
            download_url=spec.url,
        )
    return BundledFontPackage(
        pubspec_family=entry.pubspec_family,
        zip_url=None,
        weight_files=weight_files,
    )


def weight_file_key(font_weight: str, font_style: str | None) -> str:
    """Build lookup key for ``BundledFontPackage.weight_files``."""
    if font_style == "italic":
        return f"{font_weight}i"
    return font_weight


def pubspec_family_for_google_alias(figma_family: str, metadata_family: str) -> str:
    """Return the pubspec family name for a Google Fonts substitute."""
    registry = _registry()
    entry = registry.lookup(figma_family)
    if entry is not None:
        return entry.pubspec_family
    normalized = normalize_figma_family_key(figma_family)
    aliases = registry.pubspec_family_aliases()
    override = aliases.get(normalized) or aliases.get(normalized.replace(" ", ""))
    if override is not None:
        return override
    return metadata_family


def google_font_slug_aliases() -> dict[str, str]:
    """Return normalized Figma keys mapped to Google Fonts slugs."""
    return load_font_registry().google_slug_aliases()


# Backward-compatible module-level aliases populated from the registry.
GOOGLE_FONT_SLUG_ALIASES = google_font_slug_aliases()
GOOGLE_FONT_PUBSPEC_ALIASES = load_font_registry().pubspec_family_aliases()
FIGMA_FAMILY_ALIASES = load_font_registry().figma_to_pubspec_aliases()
