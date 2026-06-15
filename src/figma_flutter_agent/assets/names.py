"""Asset filename helpers."""

from __future__ import annotations

import re
from typing import Literal

SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")

_SvgExportKind = Literal["icon", "boundary_svg"]


def safe_filename(name: str) -> str:
    cleaned = SAFE_NAME.sub("_", name.strip().lower()).strip("_")
    return cleaned or "asset"


def asset_filename(name: str, node_id: str, extension: str) -> str:
    """Build a collision-safe asset filename using the Figma node id."""
    node_suffix = node_id.replace(":", "_")
    return f"{safe_filename(name)}_{node_suffix}.{extension}"


def expected_svg_export_rel_path(
    name: str,
    node_id: str,
    kind: _SvgExportKind,
) -> str:
    """Return the relative Flutter asset path for a planned SVG export.

    Args:
        name: Figma layer name used in ``asset_filename``.
        node_id: Figma node id suffix.
        kind: ``icon`` maps to ``assets/icons/``; ``boundary_svg`` to
            ``assets/illustrations/``.

    Returns:
        Project-relative path such as ``assets/icons/back_103_584.svg``.
    """
    filename = asset_filename(name, node_id, "svg")
    folder = "illustrations" if kind == "boundary_svg" else "icons"
    return f"assets/{folder}/{filename}"
