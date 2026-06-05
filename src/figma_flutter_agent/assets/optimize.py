"""Optional asset optimization helpers."""

from __future__ import annotations

import re

_XML_DECL_RE = re.compile(r"<\?xml[^?]*\?>\s*", re.IGNORECASE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


def svg_path_element_count(content: str) -> int:
    """Count path-like SVG elements for raster-vs-vector complexity heuristics (FID-46)."""
    lowered = content.lower()
    return sum(
        lowered.count(f"<{tag}")
        for tag in ("path", "circle", "rect", "ellipse", "polygon", "polyline", "line")
    )


def svg_has_unsupported_filter(content: str) -> bool:
    """Return True when SVG uses Gaussian blur filters unsupported by flutter_svg."""
    lowered = content.lower()
    return "<filter" in lowered or "fegaussianblur" in lowered


def optimize_svg(content: str) -> str:
    """Apply lightweight deterministic SVG cleanup.

    Args:
        content: Raw SVG markup.

    Returns:
        Minified SVG markup safe for Flutter asset bundling.
    """
    normalized = content.strip()
    normalized = _XML_DECL_RE.sub("", normalized)
    normalized = _COMMENT_RE.sub("", normalized)
    normalized = _MULTI_SPACE_RE.sub(" ", normalized)
    return normalized.replace("> <", "><").strip()
