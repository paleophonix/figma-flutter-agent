"""Download and install bundled font files into a Flutter project."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import httpx
from loguru import logger

from figma_flutter_agent.fonts.cache import read_cached_font, write_cached_font
from figma_flutter_agent.fonts.collector import collect_font_faces
from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.local import ensure_project_fonts_dir
from figma_flutter_agent.fonts.models import ResolvedFontAsset
from figma_flutter_agent.fonts.paths import (
    is_valid_font_bytes,
    project_fonts_dir,
    pubspec_font_asset_path,
)
from figma_flutter_agent.fonts.resolver import resolve_font_face
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
    """Download resolved font files into ``assets/fonts/``."""
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets.values():
        target = fonts_dir / asset.asset_name
        if target.is_file():
            if _is_usable_font_file(target):
                logger.debug("Font asset already present: {}", target.as_posix())
                continue
            logger.warning(
                "Replacing invalid font file at {} (not a valid TTF/OTF; re-downloading)",
                target.as_posix(),
            )
            target.unlink()
        if asset.local_path is not None:
            if not _is_usable_font_file(asset.local_path):
                logger.warning(
                    "Skipping invalid local font at {}",
                    asset.local_path.as_posix(),
                )
                continue
            if asset.local_path.resolve() != target.resolve():
                shutil.copy2(asset.local_path, target)
                logger.info(
                    "Copied local font {} -> {}",
                    asset.local_path.as_posix(),
                    target.as_posix(),
                )
            else:
                logger.debug("Using in-place local font: {}", target.as_posix())
            continue
        if not asset.download_url:
            continue
        payload = _fetch_font_bytes(
            asset.download_url,
            client=client,
            session_cache=session_cache,
            cache_enabled=cache_enabled,
        )
        if not is_valid_font_bytes(payload):
            logger.warning(
                "Downloaded font for '{}' is not a valid TTF/OTF; skipped {}",
                asset.figma_family,
                asset.asset_name,
            )
            continue
        target.write_bytes(payload)
        logger.info("Bundled font asset written: {}", target.as_posix())


def _is_usable_font_file(path: Path) -> bool:
    try:
        return is_valid_font_bytes(path.read_bytes())
    except OSError:
        return False


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
            asset=pubspec_font_asset_path(asset.asset_name),
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
    project_dir: Path,
    download_fonts: bool,
    phase: Literal["fetch", "run"],
) -> tuple[list[ResolvedFontAsset], list[str]]:
    """Resolve and deduplicate downloadable font assets for ``faces``."""
    warnings: list[str] = []
    assets_by_key: dict[tuple[str, int, str | None], ResolvedFontAsset] = {}

    for face in faces:
        resolved, warning = resolve_font_face(
            face,
            client=client,
            context=context,
            project_dir=project_dir,
            download_fonts=download_fonts,
            phase=phase,
        )
        if warning:
            warnings.append(warning)
        if resolved is None:
            continue
        dedupe_key = (resolved.pubspec_family, resolved.weight, resolved.style)
        assets_by_key[dedupe_key] = resolved

    return list(assets_by_key.values()), warnings


def bundle_fonts_for_tree(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    *,
    enabled: bool = True,
    download_fonts: bool = False,
    cache_enabled: bool = True,
    phase: Literal["fetch", "run"] = "run",
) -> FontManifest:
    """Download bundled fonts required by ``tree`` and return a manifest.

    Args:
        tree: Parsed clean design tree.
        project_dir: Flutter project root.
        enabled: When False, returns an empty manifest without downloading.
        download_fonts: When False, only use files already in ``assets/fonts/``.
        cache_enabled: When True, reuse ``~/.config/figma-flutter-agent/cache/fonts``.
        phase: ``fetch`` after import, ``run`` during generation.

    Returns:
        Font manifest describing bundled pubspec families.
    """
    if not enabled:
        return FontManifest()

    faces = collect_font_faces(tree)
    return bundle_font_faces(
        faces,
        project_dir,
        download_fonts=download_fonts,
        cache_enabled=cache_enabled,
        phase=phase,
    )


def bundle_font_faces(
    faces: list[FontFaceRequirement],
    project_dir: Path,
    *,
    download_fonts: bool = False,
    cache_enabled: bool = True,
    phase: Literal["fetch", "run"] = "run",
) -> FontManifest:
    """Resolve and optionally download fonts for explicit face requirements."""
    if not faces:
        return FontManifest()

    ensure_project_fonts_dir(project_dir)
    context = FontResolutionContext.for_project(project_dir)
    with httpx.Client(
        timeout=DOWNLOAD_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resolutions, warnings = _resolve_faces(
            faces,
            client=client,
            context=context,
            project_dir=project_dir,
            download_fonts=download_fonts,
            phase=phase,
        )
        if not resolutions:
            return FontManifest(warnings=warnings)

        families, bundled_names, family_aliases = _build_manifest_from_resolutions(resolutions)
        fonts_dir = project_fonts_dir(project_dir)
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
