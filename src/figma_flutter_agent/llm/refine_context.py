"""Structured context helpers for LLM visual refine passes."""

from __future__ import annotations

import re
from typing import Any

from figma_flutter_agent.llm.refine_models import (
    RefineAttemptSummary,
    RefineFocus,
    resolve_refine_focus,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse, NodeType

__all__ = [
    "RefineAttemptSummary",
    "RefineFocus",
    "resolve_refine_focus",
]

_INTERACTIVE_TYPES: frozenset[NodeType] = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
        NodeType.CAROUSEL,
    }
)

_SCROLL_TYPES: frozenset[NodeType] = frozenset({NodeType.GRID, NodeType.CAROUSEL})

_HANDLER_PATTERNS: dict[NodeType, tuple[str, ...]] = {
    NodeType.BUTTON: (r"onPressed\s*:\s*(?!null\b)", r"onTap\s*:\s*(?!null\b)"),
    NodeType.INPUT: (r"onChanged\s*:", r"TextEditingController\s*\(", r"controller\s*:"),
    NodeType.CHECKBOX: (r"onChanged\s*:\s*(?!null\b)", r"Checkbox\s*\("),
    NodeType.SWITCH: (r"onChanged\s*:\s*(?!null\b)", r"Switch\s*\("),
    NodeType.RADIO: (r"onChanged\s*:\s*(?!null\b)", r"Radio\s*\("),
    NodeType.RADIO_GROUP: (r"onChanged\s*:\s*(?!null\b)", r"Radio\s*\("),
    NodeType.DROPDOWN: (r"onChanged\s*:\s*(?!null\b)", r"DropdownButton\s*\("),
    NodeType.SLIDER: (r"onChanged\s*:\s*(?!null\b)", r"Slider\s*\("),
    NodeType.TABS: (r"TabController", r"onTap\s*:", r"DefaultTabController"),
    NodeType.BOTTOM_NAV: (r"BottomNavigationBar\s*\(", r"onTap\s*:"),
    NodeType.CAROUSEL: (r"PageView\s*\(", r"onPageChanged\s*:"),
}

_EXPECTED_HANDLER: dict[NodeType, str] = {
    NodeType.BUTTON: "onPressed/onTap",
    NodeType.INPUT: "onChanged/controller",
    NodeType.CHECKBOX: "onChanged",
    NodeType.SWITCH: "onChanged",
    NodeType.RADIO: "onChanged",
    NodeType.RADIO_GROUP: "onChanged",
    NodeType.DROPDOWN: "onChanged",
    NodeType.SLIDER: "onChanged",
    NodeType.TABS: "TabController/onTap",
    NodeType.BOTTOM_NAV: "onTap",
    NodeType.CAROUSEL: "PageView/onPageChanged",
}


def build_interactive_inventory(clean_tree: CleanDesignTreeNode) -> list[dict[str, Any]]:
    """Collect interactive nodes from the clean design tree.

    Args:
        clean_tree: Parsed screen tree.

    Returns:
        Flat inventory entries with node id, semantic type, and variant metadata.
    """
    inventory: list[dict[str, Any]] = []

    def _walk(node: CleanDesignTreeNode) -> None:
        node_type = node.type
        is_interactive = node_type in _INTERACTIVE_TYPES
        is_scroll = node_type in _SCROLL_TYPES or node.scroll_axis not in ("none",)
        if is_interactive or is_scroll:
            variant_state = None
            if node.variant is not None:
                variant_state = node.variant.state or node.variant.variant_properties.get("State")
            entry: dict[str, Any] = {
                "nodeId": node.id,
                "name": node.name,
                "type": node_type.value,
                "expectedHandler": _EXPECTED_HANDLER.get(node_type, "onTap/onChanged"),
            }
            if node.text:
                entry["labelText"] = node.text
            if variant_state:
                entry["variantState"] = variant_state
            if node.scroll_axis not in ("none",):
                entry["scrollAxis"] = node.scroll_axis
            inventory.append(entry)
        for child in node.children:
            _walk(child)

    _walk(clean_tree)
    return inventory


def _combined_generation_dart(generation: FlutterGenerationResponse) -> str:
    parts: list[str] = []
    screen_code = generation.resolved_screen_code()
    if screen_code:
        parts.append(screen_code)
    parts.extend(
        widget.resolved_code() for widget in generation.extracted_widgets if widget.resolved_code()
    )
    return "\n".join(parts)


def _count_handler_matches(code: str, node_type: NodeType) -> int:
    patterns = _HANDLER_PATTERNS.get(node_type, ())
    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, code, flags=re.MULTILINE))
    return total


def audit_interaction_handlers(
    inventory: list[dict[str, Any]],
    generation: FlutterGenerationResponse,
) -> dict[str, Any]:
    """Audit generated Dart for missing interaction handlers.

    Args:
        inventory: Output of ``build_interactive_inventory``.
        generation: Current LLM generation payload.

    Returns:
        Handler audit summary for the visual refine JSON payload.
    """
    combined = _combined_generation_dart(generation)
    counts_by_type: dict[str, int] = {}
    handler_counts_by_type: dict[str, int] = {}
    for entry in inventory:
        node_type = NodeType(entry["type"])
        counts_by_type[node_type.value] = counts_by_type.get(node_type.value, 0) + 1

    for node_type in _INTERACTIVE_TYPES:
        handler_counts_by_type[node_type.value] = _count_handler_matches(combined, node_type)

    missing_handlers: list[str] = []
    for entry in inventory:
        node_type = NodeType(entry["type"])
        if node_type not in _HANDLER_PATTERNS:
            continue
        inventory_count = counts_by_type.get(node_type.value, 0)
        handler_count = handler_counts_by_type.get(node_type.value, 0)
        if inventory_count == 0:
            continue
        if handler_count < inventory_count:
            label = entry.get("labelText") or entry["name"]
            missing_handlers.append(f"{entry['type']}:{label} ({entry['nodeId']})")

    decorative_only: list[str] = []
    decorative_patterns = (
        r"GestureDetector\s*\(\s*(?!.*onTap)",
        r"InkWell\s*\(\s*(?!.*onTap)",
        r"IconButton\s*\(\s*(?!.*onPressed)",
    )
    for pattern in decorative_patterns:
        for match in re.finditer(pattern, combined, flags=re.DOTALL):
            snippet = combined[max(0, match.start() - 20) : match.start() + 40].replace("\n", " ")
            decorative_only.append(snippet.strip()[:80])

    return {
        "inventoryCountsByType": counts_by_type,
        "handlerCountsByType": handler_counts_by_type,
        "missingHandlers": missing_handlers[:12],
        "decorativeOnlyHints": decorative_only[:6],
        "passedInteractionAudit": not missing_handlers and not decorative_only,
    }


def build_asset_warnings(
    *,
    clean_tree: CleanDesignTreeNode,
    asset_manifest: list[dict[str, str]],
) -> list[str]:
    """Build asset-related warnings that pixel diff cannot explain.

    Args:
        clean_tree: Parsed screen tree.
        asset_manifest: Exported asset metadata entries.

    Returns:
        Warning strings for the visual refine payload.
    """
    warnings: list[str] = []

    def _walk(node: CleanDesignTreeNode) -> None:
        if node.vector_svg_has_filter:
            key = node.vector_asset_key or node.name
            warnings.append(f"SVG filter unsupported in Flutter for asset '{key}'")
        for child in node.children:
            _walk(child)

    _walk(clean_tree)
    for entry in asset_manifest:
        if entry.get("svgHasFilter") or entry.get("svg_has_filter"):
            path = entry.get("path") or entry.get("assetKey") or "unknown"
            message = f"SVG filter in manifest asset '{path}' may not render in Flutter"
            if message not in warnings:
                warnings.append(message)
    return warnings[:10]


_FOREGROUND_ANCHOR_TYPES: frozenset[NodeType] = frozenset(
    {
        NodeType.TEXT,
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
        NodeType.CARD,
        NodeType.ROW,
        NodeType.COLUMN,
        NodeType.CONTAINER,
        NodeType.STACK,
    }
)

_DECORATIVE_ASSET_TYPES: frozenset[NodeType] = frozenset({NodeType.VECTOR, NodeType.IMAGE})


def build_foreground_layout_anchors(clean_tree: CleanDesignTreeNode) -> list[dict[str, Any]]:
    """Collect absolute foreground layout anchors from a STACK-based clean tree.

    Args:
        clean_tree: Parsed screen tree root.

    Returns:
        Ordered anchor entries with Figma stackPlacement coordinates for foreground UI.
    """
    anchors: list[dict[str, Any]] = []

    def _walk(node: CleanDesignTreeNode) -> None:
        node_type = node.type
        if node_type in _DECORATIVE_ASSET_TYPES and (node.vector_asset_key or node.image_asset_key):
            for child in node.children:
                _walk(child)
            return
        placement = node.stack_placement
        if placement is not None and node_type in _FOREGROUND_ANCHOR_TYPES:
            anchor: dict[str, Any] = {
                "nodeId": node.id,
                "name": node.name,
                "type": node_type.value,
                "left": placement.left,
                "top": placement.top,
            }
            width = placement.width if placement.width is not None else node.sizing.width
            height = placement.height if placement.height is not None else node.sizing.height
            if width is not None:
                anchor["width"] = width
            if height is not None:
                anchor["height"] = height
            if node.text:
                anchor["labelText"] = node.text
            anchors.append(anchor)
        for child in node.children:
            _walk(child)

    _walk(clean_tree)
    anchors.sort(key=lambda entry: (float(entry.get("top", 0)), float(entry.get("left", 0))))
    return anchors[:24]


def build_canvas_size(clean_tree: CleanDesignTreeNode) -> dict[str, float | int]:
    """Return golden capture canvas size derived from the root frame.

    Args:
        clean_tree: Parsed screen tree root.

    Returns:
        Width/height used for widget golden tests when available.
    """
    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    return {
        "width": int(width) if width is not None else 0,
        "height": int(height) if height is not None else 0,
    }
