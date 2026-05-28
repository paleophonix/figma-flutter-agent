"""Parse Figma anchor keys from generated Dart sources."""

from __future__ import annotations

import re

_FIGMA_KEY_RE = re.compile(r"ValueKey\(\s*'figma-([^']+)'\s*\)")


def parse_figma_key_ids(source: str) -> list[str]:
    """Return Figma node ids referenced by ``ValueKey('figma-…')`` in ``source``.

    Args:
        source: Dart widget source.

    Returns:
        Node ids with ``:`` restored from underscore form.
    """
    ids: list[str] = []
    seen: set[str] = set()
    for match in _FIGMA_KEY_RE.finditer(source):
        token = match.group(1)
        node_id = token.replace("_", ":", 1) if "_" in token and ":" not in token else token
        if node_id not in seen:
            seen.add(node_id)
            ids.append(node_id)
    return ids


def figma_id_from_key_token(token: str) -> str:
    """Map a ``figma-*`` key token back to a Figma node id."""
    if ":" in token:
        return token
    if "_" in token:
        return token.replace("_", ":", 1)
    return token
