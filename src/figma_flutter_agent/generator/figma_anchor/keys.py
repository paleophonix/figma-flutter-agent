"""Figma ValueKey anchors."""

from __future__ import annotations

import re
from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode, StackPlacement

_POSITIONED_RE = re.compile(
    r"Positioned\s*\(\s*(?P<args>.*?)\s*,\s*child:\s*",
    re.DOTALL,
)
def _normalize_layout_block_for_screen_embed(block: str) -> str:
    """Inline layout ``textScaler`` locals when splicing blocks into a screen ``build``."""
    if "textScaler: textScaler" not in block:
        return block
    return block.replace(
        "textScaler: textScaler",
        "textScaler: MediaQuery.textScalerOf(context)",
    )


@dataclass(frozen=True)
class PositionedAnchor:
    """One positioned widget anchor in design coordinates."""

    node_id: str
    left: float
    top: float


def figma_key_token(node_id: str) -> str:
    """Return the Dart ``ValueKey`` token suffix for a Figma node id."""
    return _sanitize_figma_key_token(node_id)


def figma_value_key_arg(node_id: str) -> str:
    """Return a Dart named argument for ``ValueKey`` tied to ``node_id``."""
    return f"key: ValueKey('{figma_key_token(node_id)}')"


def _sanitize_figma_key_token(node_id: str) -> str:
    """Return the canonical Figma key token for a node id."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", node_id)
    return f"figma-{safe or 'unknown'}"


def collect_positioned_anchors(root: CleanDesignTreeNode) -> list[PositionedAnchor]:
    """Collect nodes that have stack placement (candidates for ``Positioned``)."""

    anchors: list[PositionedAnchor] = []

    def walk(node: CleanDesignTreeNode) -> None:
        placement = node.stack_placement
        if placement is not None:
            box = _placement_box(placement)
            if box is not None:
                left, top, _width, _height = box
                anchors.append(PositionedAnchor(node_id=node.id, left=left, top=top))
        for child in node.children:
            walk(child)

    walk(root)
    return anchors


def _placement_box(placement: StackPlacement) -> tuple[float, float, float, float] | None:
    width = placement.width
    height = placement.height
    if width is None or height is None:
        return None
    return placement.left, placement.top, width, height


def _coords_in_args(args: str, left: float, top: float, *, tolerance: float = 0.6) -> bool:
    left_match = re.search(r"left:\s*([\d.]+)", args)
    top_match = re.search(r"top:\s*([\d.]+)", args)
    if left_match is None or top_match is None:
        return False
    return abs(float(left_match.group(1)) - left) <= tolerance and abs(
        float(top_match.group(1)) - top
    ) <= tolerance


def inject_figma_keys_into_screen(screen_code: str, root: CleanDesignTreeNode) -> str:
    """Insert ``ValueKey('figma-…')`` into ``Positioned`` widgets matching tree placement.

    Args:
        screen_code: Screen Dart source (LLM or deterministic).
        root: Clean design tree for coordinate matching.

    Returns:
        Updated Dart source (unchanged when no anchors match).
    """
    anchors = collect_positioned_anchors(root)
    if not anchors:
        return screen_code

    updated = screen_code
    for anchor in anchors:
        if figma_key_token(anchor.node_id) in updated:
            continue

        def _inject(match: re.Match[str], _anchor: object = anchor) -> str:
            args = match.group("args")
            if not _coords_in_args(args, _anchor.left, _anchor.top):  # type: ignore[union-attr]
                return match.group(0)
            if "key:" in args:
                return match.group(0)
            key = figma_value_key_arg(_anchor.node_id)  # type: ignore[union-attr]
            return f"Positioned({args}, {key}, child: "

        updated = _POSITIONED_RE.sub(_inject, updated, count=1)
    return updated
