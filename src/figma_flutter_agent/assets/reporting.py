"""User-facing asset export failure reporting."""

from __future__ import annotations

_MAX_LISTED_NODE_IDS = 12


def summarize_failed_asset_exports(
    failed_node_ids: frozenset[str] | set[str],
    *,
    rate_limited: bool = False,
) -> str | None:
    """Build a pipeline warning listing failed Figma node ids.

    Args:
        failed_node_ids: Node ids that could not be exported.
        rate_limited: Whether rate limiting contributed to failures.

    Returns:
        Warning text, or ``None`` when there are no failures.
    """
    if not failed_node_ids:
        return None
    ordered = sorted(failed_node_ids)
    preview = ", ".join(ordered[:_MAX_LISTED_NODE_IDS])
    if len(ordered) > _MAX_LISTED_NODE_IDS:
        preview = f"{preview} (+{len(ordered) - _MAX_LISTED_NODE_IDS} more)"
    prefix = "Asset export hit Figma rate limits and could not fetch"
    if rate_limited:
        return f"{prefix} {len(ordered)} node(s): {preview}"
    return f"Asset export could not fetch {len(ordered)} node(s) from Figma Images API: {preview}"


def log_failed_asset_exports(
    failed_node_ids: frozenset[str] | set[str],
    *,
    rate_limited: bool = False,
) -> None:
    """Emit one warning per failed node id (never demoted to debug)."""
    from loguru import logger

    if not failed_node_ids:
        return
    summary = summarize_failed_asset_exports(failed_node_ids, rate_limited=rate_limited)
    if summary is not None:
        logger.warning(summary)
    for node_id in sorted(failed_node_ids):
        logger.warning("Asset export failed for Figma node {}", node_id)
