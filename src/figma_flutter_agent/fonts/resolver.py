"""Resolve Figma font faces to downloadable bundled assets."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.googlefonts import (
    UNIVERSAL_FALLBACK_SLUG,
    family_to_slug,
    resolve_google_font_face,
    weight_token_to_int,
)
from figma_flutter_agent.fonts.sources import weight_file_key
from figma_flutter_agent.schemas import FontFaceRequirement


@dataclass(frozen=True)
class ResolvedFontAsset:
    """One downloadable font file for a resolved face."""

    figma_family: str
    pubspec_family: str
    asset_name: str
    download_url: str
    weight: int
    style: str | None
    source: str


def _asset_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", family.strip().lower()).strip("_") or "font"


def _asset_name(pubspec_family: str, weight: int, style: str | None, *, ext: str) -> str:
    style_suffix = f"_{style}" if style else ""
    return f"{_asset_slug(pubspec_family)}_{weight}{style_suffix}{ext}"


def _resolve_proprietary_face(
    face: FontFaceRequirement,
    *,
    context: FontResolutionContext,
) -> ResolvedFontAsset | None:
    entry = context.lookup(face.figma_family)
    pubspec_family = entry.pubspec_family if entry is not None else face.figma_family.strip()
    package = context.bundled_package(pubspec_family)
    if package is None:
        return None
    key = weight_file_key(face.font_weight, face.font_style)
    weight_file = package.weight_files.get(key)
    if weight_file is None or weight_file.download_url is None:
        return None
    ".otf" if weight_file.download_url.endswith(".otf") else ".ttf"
    return ResolvedFontAsset(
        figma_family=face.figma_family,
        pubspec_family=package.pubspec_family,
        asset_name=weight_file.asset_name,
        download_url=weight_file.download_url,
        weight=weight_file.weight,
        style=weight_file.style,
        source="proprietary-substitute",
    )


def resolve_font_face(
    face: FontFaceRequirement,
    *,
    client: httpx.Client | None = None,
    context: FontResolutionContext | None = None,
) -> tuple[ResolvedFontAsset | None, str | None]:
    """Resolve one Figma font face to a downloadable asset.

    Args:
        face: Required font face from the design tree.
        client: Optional shared HTTP client for Google Fonts lookups.
        context: Optional merged registry/project override context.

    Returns:
        Tuple of resolved asset and optional warning when a fallback was used.
    """
    ctx = context or FontResolutionContext.for_project(None)
    proprietary = _resolve_proprietary_face(face, context=ctx)
    if proprietary is not None:
        return proprietary, None

    entry = ctx.lookup(face.figma_family)
    profile = ctx.profile_for_family(face.figma_family)
    download_weight_token = (
        profile.effective_download_weight_token(face.font_weight) if profile else face.font_weight
    )
    forced_slug = entry.gwfh_slug if entry is not None else None
    forced_pubspec = (
        entry.pubspec_family if entry is not None and entry.strategy != "google_direct" else None
    )

    google_match = resolve_google_font_face(
        figma_family=face.figma_family,
        font_weight=face.font_weight,
        font_style=face.font_style,
        slug_aliases=ctx.google_slug_aliases(),
        client=client,
        forced_slug=forced_slug,
        forced_pubspec_family=forced_pubspec,
        download_weight_token=download_weight_token,
        pubspec_family_resolver=ctx.pubspec_family_for_figma,
    )
    if google_match is None:
        return None, (
            f"Could not auto-download font '{face.figma_family}' "
            f"({face.font_weight}{' italic' if face.font_style else ''})."
        )

    metadata, variant, pubspec_family = google_match
    weight = weight_token_to_int(face.font_weight)
    if profile is not None:
        weight = profile.effective_pubspec_weight(face.font_weight)
    style = face.font_style if face.font_style == "italic" else None
    warning: str | None = None
    if int(variant.get("fontWeight", weight)) != weight or variant.get("fontStyle") != (
        style or "normal"
    ):
        warning = (
            f"Font '{face.figma_family}' used nearest Google Fonts variant "
            f"{variant.get('fontWeight')} {variant.get('fontStyle')} from '{metadata.get('family')}'."
        )

    if (
        metadata.get("id") == UNIVERSAL_FALLBACK_SLUG
        and family_to_slug(face.figma_family) != UNIVERSAL_FALLBACK_SLUG
    ):
        warning = (
            f"Font '{face.figma_family}' is unavailable for auto-download; "
            f"using Noto Sans files registered under '{pubspec_family}'."
        )

    return (
        ResolvedFontAsset(
            figma_family=face.figma_family,
            pubspec_family=pubspec_family,
            asset_name=_asset_name(pubspec_family, weight, style, ext=".ttf"),
            download_url=str(variant["ttf"]),
            weight=int(variant.get("fontWeight", weight)),
            style=style,
            source="google-fonts",
        ),
        warning,
    )
