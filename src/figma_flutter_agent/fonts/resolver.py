"""Resolve Figma font faces to downloadable bundled assets."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import httpx

from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.models import ResolvedFontAsset

__all__ = ["ResolvedFontAsset", "resolve_font_face"]
from figma_flutter_agent.fonts.local import (
    expected_asset_name,
    find_local_analog_font_file,
    find_local_original_font_file,
)
from figma_flutter_agent.fonts.naming_hint import (
    analog_usage_warning,
    append_rename_hint,
    format_substitute_offer,
)
from figma_flutter_agent.fonts.offers import peek_substitute_asset, substitute_source_label
from figma_flutter_agent.schemas import FontFaceRequirement


def _asset_name(pubspec_family: str, weight: int, style: str | None, *, ext: str) -> str:
    return expected_asset_name(pubspec_family, weight, style, ext=ext)


def _resolved_from_local_file(
    face: FontFaceRequirement,
    path: Path,
    *,
    pubspec_family: str | None = None,
    is_analog: bool = False,
) -> ResolvedFontAsset:
    from figma_flutter_agent.fonts.googlefonts import weight_token_to_int

    weight = weight_token_to_int(face.font_weight)
    style = face.font_style if face.font_style == "italic" else None
    family = (pubspec_family or face.figma_family).strip()
    ext = path.suffix.lower() if path.suffix else ".ttf"
    if is_analog or path.stem.endswith("_analog"):
        asset_name = path.name
        source = "local-analog"
    else:
        asset_name = _asset_name(family, weight, style, ext=ext)
        source = "local"
    return ResolvedFontAsset(
        figma_family=face.figma_family,
        pubspec_family=family,
        asset_name=asset_name,
        download_url="",
        weight=weight,
        style=style,
        source=source,
        local_path=path.resolve(),
        is_analog=is_analog or path.stem.endswith("_analog"),
    )


def _missing_font_warning(
    face: FontFaceRequirement,
    *,
    phase: Literal["fetch", "run"],
    on_google: bool,
    download_fonts: bool,
    pubspec_family: str | None = None,
) -> str:
    weight_label = f"{face.font_weight}{' italic' if face.font_style else ''}"
    if phase == "fetch":
        if on_google and not download_fonts:
            return append_rename_hint(
                (
                    f"Font '{face.figma_family}' ({weight_label}) is not in assets/fonts/; "
                    "a substitute is available on Google Fonts (enable fonts.download_fonts to "
                    "download, or add the original file)."
                ),
                face,
                pubspec_family=pubspec_family,
            )
        if on_google:
            return append_rename_hint(
                (
                    f"Font '{face.figma_family}' ({weight_label}) is not in assets/fonts/ "
                    "and could not be downloaded."
                ),
                face,
                pubspec_family=pubspec_family,
            )
        return append_rename_hint(
            (
                f"Font '{face.figma_family}' ({weight_label}) was not found in assets/fonts/ "
                "or on Google Fonts. Add the original font file to assets/fonts/ for accurate "
                "conversion."
            ),
            face,
            pubspec_family=pubspec_family,
        )
    if on_google and not download_fonts:
        return append_rename_hint(
            (
                f"Font '{face.figma_family}' ({weight_label}) is not bundled; a substitute is "
                "available (enable fonts.download_fonts to download, or add the original to "
                "assets/fonts/)."
            ),
            face,
            pubspec_family=pubspec_family,
        )
    if on_google:
        return append_rename_hint(
            (
                f"Font '{face.figma_family}' ({weight_label}) is not bundled; a substitute "
                "or system fallback may be used at run time. Add the original to assets/fonts/ "
                "or enable fonts.download_fonts."
            ),
            face,
            pubspec_family=pubspec_family,
        )
    return append_rename_hint(
        (
            f"Font '{face.figma_family}' ({weight_label}) was not found in assets/fonts/ "
            "or on Google Fonts; a theme/system fallback may be used at run time. Add the "
            "original font file to assets/fonts/ for accurate conversion."
        ),
        face,
        pubspec_family=pubspec_family,
    )


def resolve_font_face(
    face: FontFaceRequirement,
    *,
    client: httpx.Client | None = None,
    context: FontResolutionContext | None = None,
    project_dir: Path | None = None,
    download_fonts: bool = False,
    phase: Literal["fetch", "run"] = "run",
) -> tuple[ResolvedFontAsset | None, str | None]:
    """Resolve one Figma font face: original on disk → analog on disk → optional download.

    When ``download_fonts`` is False, substitutes are only reported (not fetched).
    Downloaded substitutes use the ``*_analog`` suffix. A warning is always returned when
    an analog substitute is used.
    """
    ctx = context or FontResolutionContext.for_project(project_dir)
    entry = ctx.lookup(face.figma_family)
    pubspec_family = entry.pubspec_family if entry is not None else face.figma_family.strip()

    if project_dir is not None:
        original_path = find_local_original_font_file(
            face, project_dir, pubspec_family=pubspec_family
        )
        if original_path is not None:
            return _resolved_from_local_file(
                face,
                original_path,
                pubspec_family=pubspec_family,
                is_analog=False,
            ), None

        analog_path = find_local_analog_font_file(face, project_dir, pubspec_family=pubspec_family)
        if analog_path is not None:
            return _resolved_from_local_file(
                face,
                analog_path,
                pubspec_family=pubspec_family,
                is_analog=True,
            ), analog_usage_warning(
                face,
                pubspec_family=pubspec_family,
                substitute_label="on disk",
                saved_as=analog_path.name,
            )

    substitute, on_google = peek_substitute_asset(
        face,
        context=ctx,
        project_dir=project_dir,
        client=client,
    )
    if substitute is None:
        return None, _missing_font_warning(
            face,
            phase=phase,
            on_google=on_google,
            download_fonts=download_fonts,
            pubspec_family=pubspec_family,
        )

    if not download_fonts:
        return None, format_substitute_offer(
            face,
            pubspec_family=substitute.pubspec_family,
            asset_name=substitute.asset_name,
            source_label=substitute_source_label(substitute, context=ctx),
        )

    return substitute, analog_usage_warning(
        face,
        pubspec_family=substitute.pubspec_family,
        substitute_label=substitute_source_label(substitute, context=ctx),
        saved_as=substitute.asset_name,
    )
