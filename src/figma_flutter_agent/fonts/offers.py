"""Describe font substitutes available for download without fetching them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.googlefonts import resolve_google_font_face, weight_token_to_int
from figma_flutter_agent.fonts.local import (
    classify_local_font_match,
    expected_analog_asset_name,
    find_local_analog_font_file,
    find_local_original_font_file,
)
from figma_flutter_agent.fonts.models import ResolvedFontAsset
from figma_flutter_agent.fonts.naming_hint import format_substitute_offer
from figma_flutter_agent.fonts.sources import weight_file_key
from figma_flutter_agent.schemas import FontFaceRequirement


def _analog_asset_name(pubspec_family: str, weight: int, style: str | None, *, ext: str) -> str:
    return expected_analog_asset_name(pubspec_family, weight, style, ext=ext)


def _to_analog_asset_name(asset_name: str) -> str:
    path = Path(asset_name)
    if path.stem.endswith("_analog"):
        return asset_name
    return f"{path.stem}_analog{path.suffix or '.ttf'}"


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
    analog_name = _to_analog_asset_name(weight_file.asset_name)
    return ResolvedFontAsset(
        figma_family=face.figma_family,
        pubspec_family=package.pubspec_family,
        asset_name=analog_name,
        download_url=weight_file.download_url,
        weight=weight_file.weight,
        style=weight_file.style,
        source="proprietary-substitute",
        is_analog=True,
    )


@dataclass(frozen=True)
class FontDownloadOffer:
    """A substitute font the agent can download when enabled."""

    face: FontFaceRequirement
    asset_name: str
    pubspec_family: str
    source_label: str


def peek_substitute_asset(
    face: FontFaceRequirement,
    *,
    context: FontResolutionContext,
    project_dir: Path | None = None,
    client: httpx.Client | None = None,
) -> tuple[ResolvedFontAsset | None, bool]:
    """Return a substitute asset if one exists remotely; second flag is Google availability."""
    entry = context.lookup(face.figma_family)
    pubspec_family = entry.pubspec_family if entry is not None else face.figma_family.strip()

    if project_dir is not None:
        if find_local_original_font_file(face, project_dir, pubspec_family=pubspec_family):
            return None, False
        if find_local_analog_font_file(face, project_dir, pubspec_family=pubspec_family):
            return None, False

    proprietary = _resolve_proprietary_face(face, context=context)
    if proprietary is not None:
        return proprietary, False

    profile = context.profile_for_family(face.figma_family)
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
        slug_aliases=context.google_slug_aliases(),
        client=client,
        forced_slug=forced_slug,
        forced_pubspec_family=forced_pubspec,
        download_weight_token=download_weight_token,
        pubspec_family_resolver=context.pubspec_family_for_figma,
    )
    if google_match is None:
        return None, False

    metadata, variant, resolved_pubspec = google_match
    weight = weight_token_to_int(face.font_weight)
    if profile is not None:
        weight = profile.effective_pubspec_weight(face.font_weight)
    style = face.font_style if face.font_style == "italic" else None
    analog_name = _analog_asset_name(resolved_pubspec, weight, style, ext=".ttf")
    return (
        ResolvedFontAsset(
            figma_family=face.figma_family,
            pubspec_family=resolved_pubspec,
            asset_name=analog_name,
            download_url=str(variant["ttf"]),
            weight=int(variant.get("fontWeight", weight)),
            style=style,
            source="google-fonts-analog",
            is_analog=True,
        ),
        True,
    )


def substitute_source_label(
    asset: ResolvedFontAsset,
    *,
    context: FontResolutionContext,
) -> str:
    """Human-readable substitute source for offers and warnings."""
    if asset.source == "proprietary-substitute":
        entry = context.lookup(asset.figma_family)
        name = entry.substitute_name if entry is not None and entry.substitute_name else "registry"
        return f"registry substitute ({name})"
    if asset.source == "google-fonts-analog":
        return "Google Fonts"
    return asset.source


def collect_font_download_offers(
    faces: tuple[FontFaceRequirement, ...] | list[FontFaceRequirement],
    project_dir: Path,
    *,
    client: httpx.Client | None = None,
) -> list[FontDownloadOffer]:
    """List substitutes that could be downloaded for faces not satisfied on disk."""
    context = FontResolutionContext.for_project(project_dir)
    offers: list[FontDownloadOffer] = []
    for face in faces:
        entry = context.lookup(face.figma_family)
        pubspec = entry.pubspec_family if entry is not None else None
        match = classify_local_font_match(face, project_dir, pubspec_family=pubspec)
        if match.kind != "missing":
            continue
        asset, _on_google = peek_substitute_asset(
            face,
            context=context,
            project_dir=project_dir,
            client=client,
        )
        if asset is None:
            continue
        offers.append(
            FontDownloadOffer(
                face=face,
                asset_name=asset.asset_name,
                pubspec_family=asset.pubspec_family,
                source_label=substitute_source_label(asset, context=context),
            )
        )
    return offers


def format_download_offer_line(offer: FontDownloadOffer) -> str:
    """One-line wizard/doctor hint for a downloadable substitute."""
    return format_substitute_offer(
        offer.face,
        pubspec_family=offer.pubspec_family,
        asset_name=offer.asset_name,
        source_label=offer.source_label,
    )
