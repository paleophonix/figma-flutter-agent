"""Generic interaction signals for LLM semantic classification."""

from __future__ import annotations

import re
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode

_CHIP_NAME_RE = re.compile(r"(chip|pill|tag|amount|сумм)", re.IGNORECASE)
_INPUT_NAME_RE = re.compile(r"(input|field|textfield|ввод)", re.IGNORECASE)
_DIVIDER_NAME_RE = re.compile(r"(divider|separator|раздел)", re.IGNORECASE)

_PILL_MIN_HEIGHT = 24.0
_PILL_MAX_HEIGHT = 56.0


def collect_interaction_signals(root: CleanDesignTreeNode) -> dict[str, dict[str, Any]]:
    """Collect geometry and naming hints keyed by Figma node id.

    Args:
        root: Clean design tree root.

    Returns:
        Map of node id to signal dictionaries for LLM payload injection.
    """
    signals: dict[str, dict[str, Any]] = {}

    def walk(node: CleanDesignTreeNode, siblings: list[CleanDesignTreeNode]) -> None:
        payload: dict[str, Any] = {"nodeType": node.type.value}
        width = node.sizing.width
        height = node.sizing.height
        if width is not None:
            payload["width"] = width
        if height is not None:
            payload["height"] = height
        if node.style.border_radius is not None:
            payload["borderRadius"] = node.style.border_radius
        if _CHIP_NAME_RE.search(node.name):
            payload["nameHint"] = "chip"
        elif _INPUT_NAME_RE.search(node.name):
            payload["nameHint"] = "input"
        elif _DIVIDER_NAME_RE.search(node.name):
            payload["nameHint"] = "divider"
        if (
            height is not None
            and _PILL_MIN_HEIGHT <= float(height) <= _PILL_MAX_HEIGHT
            and width is not None
            and float(width) > float(height)
        ):
            payload["pillLike"] = True
        if siblings:
            same_type = [item for item in siblings if item.type == node.type]
            if len(same_type) >= 2:
                payload["homogeneousSiblingGroup"] = len(same_type)
        if payload.keys() != {"nodeType"}:
            signals[node.id] = payload
        for child in node.children:
            walk(child, node.children)

    walk(root, [])
    return signals
