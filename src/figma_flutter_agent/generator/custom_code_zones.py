"""Stable custom-code zone identifiers keyed by Figma node id."""

from __future__ import annotations

_LEGACY_ROLE_NAMES = frozenset(
    {
        "button-action",
        "slider-action",
        "toggle-action",
        "back-nav",
        "card-action",
        "bottom-nav",
        "weekday-chip",
        "time-wheel",
    }
)


def _figma_key_token(node_id: str) -> str:
    """Return the ``ValueKey`` token suffix for a Figma node id (matches ``figma_anchor``)."""
    safe = node_id.replace(":", "_").replace("'", r"\'")
    return f"figma-{safe}"


def custom_code_zone_id(node_id: str, role: str | None = None) -> str:
    """Return a preservation zone name anchored to ``node_id``.

    Args:
        node_id: Figma node id (may contain ``:``).
        role: Optional semantic suffix (e.g. ``button-action``) for readability.

    Returns:
        Zone id such as ``figma-1_3608`` or ``figma-1_3608:button-action``.
    """
    base = _figma_key_token(node_id)
    if role:
        return f"{base}:{role}"
    return base


def inline_custom_code_comment(zone_id: str) -> str:
    """Return an inline Dart comment marking a custom-code zone."""
    return f"/* <custom-code:{zone_id}> */"


def block_custom_code_open(zone_id: str) -> str:
    """Return an opening line marker for a block custom-code zone."""
    return f"// <custom-code:{zone_id}>"


def block_custom_code_close(zone_id: str) -> str:
    """Return a closing line marker for a block custom-code zone."""
    return f"// </custom-code:{zone_id}>"


def legacy_role_from_zone(zone_name: str) -> str | None:
    """Return a legacy role suffix when ``zone_name`` uses the old naming scheme."""
    if zone_name in _LEGACY_ROLE_NAMES:
        return zone_name
    if ":" in zone_name:
        suffix = zone_name.rsplit(":", 1)[-1]
        if suffix in _LEGACY_ROLE_NAMES:
            return suffix
    return None


def is_legacy_role_zone(zone_name: str) -> bool:
    """Return True when ``zone_name`` is a legacy role-only zone (no figma prefix)."""
    return zone_name in _LEGACY_ROLE_NAMES
