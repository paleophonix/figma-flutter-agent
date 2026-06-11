"""Accessibility analysis helpers for clean design trees."""

from __future__ import annotations

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_WCAG_AA_MIN_RATIO = 4.5
_MIN_FONT_SIZE = 12.0
_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.DIALOG,
        NodeType.SLIDER,
        NodeType.CAROUSEL,
        NodeType.IMAGE,
        NodeType.VECTOR,
    }
)


_SKIP_CONTROL_MAX_EXTENT_PX = 120.0


def _is_skip_control_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack pairs an arc vector icon with a numeric label."""
    if node.type != NodeType.STACK:
        return False
    stack_width = node.sizing.width
    stack_height = node.sizing.height
    if stack_width is None or stack_height is None:
        return False
    if (
        float(stack_width) > _SKIP_CONTROL_MAX_EXTENT_PX
        or float(stack_height) > _SKIP_CONTROL_MAX_EXTENT_PX
    ):
        return False
    has_vector = any(
        child.type == NodeType.VECTOR
        and (child.vector_asset_key or child.style.has_stroke)
        for child in node.children
    )
    numeric_labels = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip().isdigit()
    ]
    if len(numeric_labels) != 1:
        return False
    return has_vector


def _channel(value: int) -> float:
    normalized = value / 255.0
    if normalized <= 0.03928:
        return normalized / 12.92
    return float(((normalized + 0.055) / 1.055) ** 2.4)


def _relative_luminance(argb_hex: str) -> float:
    """Compute WCAG relative luminance from ``0xAARRGGBB`` hex."""
    hex_value = argb_hex.removeprefix("0x")
    red = int(hex_value[2:4], 16)
    green = int(hex_value[4:6], 16)
    blue = int(hex_value[6:8], 16)
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def nearest_ancestor_fill_hex(
    node_id: str,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
) -> str | None:
    """Return the closest ancestor ``background_color`` behind a text node.

    Walks from the node's parent toward the root. Matches parse-time background
    inheritance used by ``apply_accessibility_fixes`` and contrast gates.

    Args:
        node_id: Figma node id for the text (or other) leaf.
        tree_by_id: Indexed clean tree nodes by id.
        parent_by_id: Child id to parent id map.

    Returns:
        Nearest non-empty ancestor fill hex, or ``None`` when no painted ancestor exists.
    """
    current = parent_by_id.get(node_id)
    while current is not None:
        ancestor = tree_by_id.get(current)
        if ancestor is None:
            break
        fill = ancestor.style.background_color
        if fill:
            return fill
        current = parent_by_id.get(current)
    return None


def contrast_ratio(foreground_hex: str, background_hex: str) -> float:
    """Compute WCAG contrast ratio between two ``0xAARRGGBB`` colors."""
    fg = _relative_luminance(foreground_hex)
    bg = _relative_luminance(background_hex)
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def _best_contrast_foreground(background_hex: str) -> str:
    """Return black or white foreground with higher contrast on the background."""
    black_ratio = contrast_ratio("0xFF000000", background_hex)
    white_ratio = contrast_ratio("0xFFFFFFFF", background_hex)
    return "0xFF000000" if black_ratio >= white_ratio else "0xFFFFFFFF"


def readable_foreground_hex(
    background_hex: str,
    preferred_foreground: str | None = None,
    *,
    min_ratio: float = _WCAG_AA_MIN_RATIO,
) -> str:
    """Pick a WCAG-readable foreground on ``background_hex`` (any design token / fill)."""
    if preferred_foreground and contrast_ratio(preferred_foreground, background_hex) >= min_ratio:
        return preferred_foreground
    return _best_contrast_foreground(background_hex)


def derive_accessibility_label(
    *,
    node_name: str,
    node_type: NodeType,
    text: str | None,
    children: list[CleanDesignTreeNode],
) -> str | None:
    """Derive an accessibility label for interactive or textual nodes."""
    if text and text.strip():
        return text.strip()

    if node_type == NodeType.BUTTON:
        for child in children:
            if child.type == NodeType.TEXT and child.text:
                return child.text.strip()

    if node_type in _INTERACTIVE_TYPES:
        cleaned = node_name.strip()
        if cleaned:
            return cleaned

    return None


def collect_accessibility_warnings(root: CleanDesignTreeNode) -> list[str]:
    """Collect contrast and font-size accessibility warnings from a clean tree."""
    warnings: list[str] = []

    def walk(node: CleanDesignTreeNode, parent_background: str | None) -> None:
        background = node.style.background_color or parent_background
        if node.type == NodeType.TEXT and node.style.text_color and background is not None:
            ratio = contrast_ratio(node.style.text_color, background)
            if ratio < _WCAG_AA_MIN_RATIO:
                warnings.append(
                    f"Low contrast on text node '{node.name}' ({ratio:.1f}:1, WCAG AA requires 4.5:1)."
                )

        if node.style.font_size is not None and node.style.font_size < _MIN_FONT_SIZE:
            warnings.append(
                f"Small font size ({node.style.font_size:g}px) on '{node.name}' may fail scalable-font guidelines."
            )

        for child in node.children:
            walk(child, background)

    walk(root, None)
    return warnings


def enforce_contrast_gates(root: CleanDesignTreeNode) -> None:
    """Raise when text nodes fail WCAG AA contrast (spec §7.9).

    Args:
        root: Parsed clean design tree.

    Raises:
        FlutterProjectError: When any text node has contrast below 4.5:1.
    """
    for message in collect_accessibility_warnings(root):
        if message.startswith("Low contrast"):
            raise FlutterProjectError(message)


def apply_accessibility_fixes(root: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Apply non-destructive accessibility fixes to a clean design tree before codegen.

    Args:
        root: Parsed clean design tree.

    Returns:
        A new tree with bumped font sizes, contrast-safe text colors, and derived labels.
    """

    def walk(
        node: CleanDesignTreeNode,
        parent_background: str | None,
        parent_node: CleanDesignTreeNode | None = None,
    ) -> CleanDesignTreeNode:
        background = node.style.background_color or parent_background
        children = [walk(child, background, node) for child in node.children]
        style = node.style.model_copy()
        accessibility_label = node.accessibility_label

        if node.type == NodeType.TEXT:
            if style.font_size is not None and style.font_size < _MIN_FONT_SIZE:
                style.font_size = _MIN_FONT_SIZE
            skip_contrast_fix = parent_node is not None and _is_skip_control_stack(parent_node)
            if style.text_color and background is not None and not skip_contrast_fix:
                ratio = contrast_ratio(style.text_color, background)
                if ratio < _WCAG_AA_MIN_RATIO:
                    style.text_color = _best_contrast_foreground(background)

        if accessibility_label is None and node.type in _INTERACTIVE_TYPES:
            accessibility_label = derive_accessibility_label(
                node_name=node.name,
                node_type=node.type,
                text=node.text,
                children=children,
            )

        return node.model_copy(
            update={
                "children": children,
                "style": style,
                "accessibility_label": accessibility_label,
            }
        )

    return walk(root, None, None)
