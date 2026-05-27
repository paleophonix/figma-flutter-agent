"""Download and install bundled font files into a Flutter project."""

from __future__ import annotations

from pathlib import Path

import httpx
from loguru import logger

from figma_flutter_agent.fonts.cache import read_cached_font, write_cached_font
from figma_flutter_agent.fonts.collector import collect_font_faces
from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.resolver import ResolvedFontAsset, resolve_font_face
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FontFaceRequirement,
    FontManifest,
    FontPubspecAsset,
    FontPubspecFamily,
)

DOWNLOAD_TIMEOUT = httpx.Timeout(120.0, connect=15.0)
_USER_AGENT = "figma-flutter-agent/0.1 (+https://github.com/figma-flutter-agent)"


def _download_bytes(url: str, *, client: httpx.Client) -> bytes:
    response = client.get(url)
    response.raise_for_status()
    return response.content


def _fetch_font_bytes(
    url: str,
    *,
    client: httpx.Client,
    session_cache: dict[str, bytes],
    cache_enabled: bool,
) -> bytes:
    """Return font bytes from session, disk cache, or remote download."""
    if url in session_cache:
        return session_cache[url]
    if cache_enabled:
        cached = read_cached_font(url)
        if cached is not None:
            logger.debug("Font cache hit for {}", url)
            session_cache[url] = cached
            return cached
    logger.info("Downloading font asset from {}", url)
    data = _download_bytes(url, client=client)
    if cache_enabled:
        write_cached_font(url, data)
    session_cache[url] = data
    return data


def _ensure_font_assets(
    *,
    fonts_dir: Path,
    assets: dict[str, ResolvedFontAsset],
    session_cache: dict[str, bytes],
    client: httpx.Client,
    cache_enabled: bool,
) -> None:
    """Download resolved font files into ``fonts/`` at the Flutter project root."""
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets.values():
        target = fonts_dir / asset.asset_name
        payload = _fetch_font_bytes(
            asset.download_url,
            client=client,
            session_cache=session_cache,
            cache_enabled=cache_enabled,
        )
        target.write_bytes(payload)
        logger.info("Bundled font asset written: {}", target.as_posix())


def _build_manifest_from_resolutions(
    resolutions: list[ResolvedFontAsset],
) -> tuple[list[FontPubspecFamily], list[str], dict[str, str]]:
    """Build pubspec families and alias map from resolved assets."""
    families_by_name: dict[str, dict[tuple[int, str | None], FontPubspecAsset]] = {}
    bundled_names: list[str] = []
    family_aliases: dict[str, str] = {}

    for asset in resolutions:
        family_aliases[asset.figma_family] = asset.pubspec_family
        pubspec_asset = FontPubspecAsset(
            asset=f"fonts/{asset.asset_name}",
            weight=asset.weight,
            style=asset.style,
        )
        family_assets = families_by_name.setdefault(asset.pubspec_family, {})
        family_assets[(pubspec_asset.weight, pubspec_asset.style)] = pubspec_asset
        if asset.pubspec_family not in bundled_names:
            bundled_names.append(asset.pubspec_family)

    families = [
        FontPubspecFamily(
            family=name,
            fonts=sorted(
                assets.values(),
                key=lambda item: (item.weight, item.style or ""),
            ),
        )
        for name, assets in sorted(families_by_name.items())
    ]
    return families, bundled_names, family_aliases


def _resolve_faces(
    faces: list[FontFaceRequirement],
    *,
    client: httpx.Client,
    context: FontResolutionContext,
) -> tuple[list[ResolvedFontAsset], list[str]]:
    """Resolve and deduplicate downloadable font assets for ``faces``."""
    warnings: list[str] = []
    assets_by_key: dict[tuple[str, int, str | None], ResolvedFontAsset] = {}

    for face in faces:
        resolved, warning = resolve_font_face(face, client=client, context=context)
        if warning:
            warnings.append(warning)
        if resolved is None:
            warnings.append(
                f"Unable to auto-download font '{face.figma_family}' "
                f"({face.font_weight}{' italic' if face.font_style else ''})."
            )
            continue
        dedupe_key = (resolved.pubspec_family, resolved.weight, resolved.style)
        assets_by_key[dedupe_key] = resolved

    return list(assets_by_key.values()), warnings


def bundle_fonts_for_tree(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    *,
    enabled: bool = True,
    cache_enabled: bool = True,
) -> FontManifest:
    """Download bundled fonts required by ``tree`` and return a manifest.

    Args:
        tree: Parsed clean design tree.
        project_dir: Flutter project root.
        enabled: When False, returns an empty manifest without downloading.
        cache_enabled: When True, reuse ``~/.config/figma-flutter-agent/cache/fonts``.

    Returns:
        Font manifest describing bundled pubspec families.
    """
    if not enabled:
        return FontManifest()

    faces = collect_font_faces(tree)
    if not faces:
        return FontManifest()

    context = FontResolutionContext.for_project(project_dir)
    with httpx.Client(
        timeout=DOWNLOAD_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resolutions, warnings = _resolve_faces(faces, client=client, context=context)
        if not resolutions:
            return FontManifest(warnings=warnings)

        families, bundled_names, family_aliases = _build_manifest_from_resolutions(resolutions)
        fonts_dir = project_dir / "fonts"
        assets_by_name = {item.asset_name: item for item in resolutions}
        _ensure_font_assets(
            fonts_dir=fonts_dir,
            assets=assets_by_name,
            session_cache={},
            client=client,
            cache_enabled=cache_enabled,
        )

    return FontManifest(
        families=families,
        bundled_family_names=bundled_names,
        family_aliases=family_aliases,
        dart_weight_overrides_by_family=context.dart_weight_overrides_for_bundled(bundled_names),
        warnings=warnings,
    )
