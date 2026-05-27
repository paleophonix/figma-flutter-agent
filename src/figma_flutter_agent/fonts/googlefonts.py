"""Google Fonts metadata and TTF download URL resolution."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
from loguru import logger

from figma_flutter_agent.fonts.sources import pubspec_family_for_google_alias

GWFH_API_URL = "https://gwfh.mranftl.com/api/fonts/{slug}"
UNIVERSAL_FALLBACK_SLUG = "noto-sans"

_metadata_cache: dict[str, dict[str, Any] | None] = {}


def family_to_slug(family: str) -> str:
    """Convert a display family name to a Google Fonts API slug."""
    collapsed = re.sub(r"[^a-zA-Z0-9]+", "-", family.strip()).strip("-").lower()
    return collapsed


def _normalize_lookup_key(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", family.strip().lower())


def fetch_google_font_metadata(
    slug: str, *, client: httpx.Client | None = None
) -> dict[str, Any] | None:
    """Fetch font metadata from the google-webfonts-helper API.

    Args:
        slug: Google Fonts slug (for example ``open-sans``).
        client: Optional shared HTTP client.

    Returns:
        Parsed metadata JSON, or ``None`` when the slug is unknown.
    """
    if slug in _metadata_cache:
        return _metadata_cache[slug]

    url = GWFH_API_URL.format(slug=slug)
    try:
        if client is None:
            with httpx.Client(follow_redirects=True, timeout=30.0) as owned:
                response = owned.get(url)
        else:
            response = client.get(url)
        if response.status_code == 404:
            _metadata_cache[slug] = None
            return None
        response.raise_for_status()
        payload = response.json()
        _metadata_cache[slug] = payload
        return payload
    except httpx.HTTPError as exc:
        logger.warning("Google Fonts metadata request failed for slug '{}': {}", slug, exc)
        _metadata_cache[slug] = None
        return None


def weight_token_to_int(font_weight: str) -> int:
    """Convert a Flutter weight token such as ``w500`` to an integer."""
    return int(font_weight.removeprefix("w"))


def pick_variant(
    variants: list[dict[str, Any]],
    *,
    weight: int,
    style: str | None,
) -> dict[str, Any] | None:
    """Pick the closest Google Fonts variant for a weight/style pair."""
    if not variants:
        return None
    desired_style = style or "normal"
    same_style = [item for item in variants if item.get("fontStyle") == desired_style]
    pool = same_style or variants
    exact = [item for item in pool if int(item.get("fontWeight", 0)) == weight]
    if exact:
        return exact[0]
    return min(pool, key=lambda item: abs(int(item.get("fontWeight", 0)) - weight))


def resolve_google_font_face(
    *,
    figma_family: str,
    font_weight: str,
    font_style: str | None,
    slug_aliases: dict[str, str],
    client: httpx.Client | None = None,
    forced_slug: str | None = None,
    forced_pubspec_family: str | None = None,
    download_weight_token: str | None = None,
    pubspec_family_resolver: Callable[[str, str], str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str] | None:
    """Resolve a Figma font face to Google Fonts metadata and a TTF variant.

    Args:
        figma_family: Raw Figma ``fontFamily`` string.
        font_weight: Flutter weight token (``w400``).
        font_style: Optional ``italic`` style.
        slug_aliases: Normalized family key to Google slug overrides.
        client: Optional shared HTTP client.
        forced_slug: Optional registry slug that must be tried first.
        forced_pubspec_family: Optional pubspec family override from the registry.
        download_weight_token: Optional weight token used when picking a variant.
        pubspec_family_resolver: Optional callback ``(figma_family, metadata_family)``.

    Returns:
        Tuple of ``(metadata, variant, pubspec_family)`` or ``None``.
    """
    weight = weight_token_to_int(download_weight_token or font_weight)
    lookup_key = _normalize_lookup_key(figma_family)
    slug_candidates: list[str] = []
    if forced_slug:
        slug_candidates.append(forced_slug)
    alias_slug = slug_aliases.get(lookup_key)
    if alias_slug is not None:
        slug_candidates.append(alias_slug)
    slug_candidates.append(family_to_slug(figma_family))
    if lookup_key and lookup_key not in slug_candidates:
        slug_candidates.append(lookup_key)

    seen: set[str] = set()
    for slug in slug_candidates:
        if not slug or slug in seen:
            continue
        seen.add(slug)
        metadata = fetch_google_font_metadata(slug, client=client)
        if metadata is None:
            continue
        variant = pick_variant(metadata.get("variants", []), weight=weight, style=font_style)
        if variant is None or not variant.get("ttf"):
            continue
        if forced_pubspec_family is not None:
            pubspec_family = forced_pubspec_family
        elif pubspec_family_resolver is not None:
            pubspec_family = pubspec_family_resolver(
                figma_family,
                str(metadata.get("family") or figma_family.strip()),
            )
        else:
            pubspec_family = pubspec_family_for_google_alias(
                figma_family,
                str(metadata.get("family") or figma_family.strip()),
            )
        return metadata, variant, pubspec_family

    fallback = fetch_google_font_metadata(UNIVERSAL_FALLBACK_SLUG, client=client)
    if fallback is None:
        return None
    variant = pick_variant(fallback.get("variants", []), weight=weight, style=font_style)
    if variant is None or not variant.get("ttf"):
        return None
    pubspec_family = figma_family.strip() or str(fallback.get("family") or "Noto Sans")
    return fallback, variant, pubspec_family


def clear_metadata_cache() -> None:
    """Clear cached Google Fonts metadata (for tests)."""
    _metadata_cache.clear()
