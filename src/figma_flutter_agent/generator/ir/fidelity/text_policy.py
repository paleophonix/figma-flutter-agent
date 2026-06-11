"""Text policy classification for baked-tier gating (EPIC 4.5 / E7 seam)."""

from __future__ import annotations

from enum import StrEnum

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

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
    }
)
_MARKETING_MIN_AREA = 40_000.0


class TextPolicyClass(StrEnum):
    """Policy class for text inside a semantic subtree."""

    LIVE_LOCALIZABLE = "live_localizable"
    LIVE_ACCESSIBILITY = "live_accessibility"
    SELECTABLE = "selectable"
    EDITABLE = "editable"
    DYNAMIC_RUNTIME = "dynamic_runtime"
    DECORATIVE_STATIC = "decorative_static"
    MARKETING_STATIC = "marketing_static"
    NONE = "none"


LIVE_BAKED_FORBIDDEN: frozenset[TextPolicyClass] = frozenset(
    {
        TextPolicyClass.LIVE_LOCALIZABLE,
        TextPolicyClass.LIVE_ACCESSIBILITY,
        TextPolicyClass.SELECTABLE,
        TextPolicyClass.EDITABLE,
        TextPolicyClass.DYNAMIC_RUNTIME,
    }
)


def _node_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return 0.0
    return float(width) * float(height)


def _has_text_descendant(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.TEXT and bool(node.text and node.text.strip()):
        return True
    return any(_has_text_descendant(child) for child in node.children)


def _collect_text_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    found: list[CleanDesignTreeNode] = []
    if node.type == NodeType.TEXT:
        found.append(node)
    for child in node.children:
        found.extend(_collect_text_nodes(child))
    return found


def primary_text_label(node: CleanDesignTreeNode) -> str | None:
    for text_node in _collect_text_nodes(node):
        if text_node.text and text_node.text.strip():
            return text_node.text.strip()
    return None


def classify_subtree_text_policy(root: CleanDesignTreeNode) -> TextPolicyClass:
    """Classify subtree text policy using structural signals only."""
    if not _has_text_descendant(root):
        return TextPolicyClass.NONE
    if root.type == NodeType.INPUT:
        return TextPolicyClass.EDITABLE
    if root.type in _INTERACTIVE_TYPES:
        return TextPolicyClass.LIVE_ACCESSIBILITY
    for child in root.children:
        if child.type == NodeType.INPUT:
            return TextPolicyClass.EDITABLE
        if child.type in _INTERACTIVE_TYPES:
            return TextPolicyClass.LIVE_ACCESSIBILITY
    text_nodes = _collect_text_nodes(root)
    if any(len((node.text or "").strip()) > 80 for node in text_nodes):
        return TextPolicyClass.LIVE_LOCALIZABLE
    if len(text_nodes) > 1:
        return TextPolicyClass.LIVE_LOCALIZABLE
    if _node_area(root) >= _MARKETING_MIN_AREA and len(text_nodes) <= 3:
        return TextPolicyClass.MARKETING_STATIC
    if text_nodes:
        return TextPolicyClass.DECORATIVE_STATIC
    return TextPolicyClass.NONE


def localization_blocker(policy: TextPolicyClass) -> bool:
    """Return True when baked text blocks localization workflows."""
    return policy in LIVE_BAKED_FORBIDDEN | {
        TextPolicyClass.MARKETING_STATIC,
        TextPolicyClass.DECORATIVE_STATIC,
    }


def baked_tier_allowed_for_policy(
    policy: TextPolicyClass,
    *,
    strict_fidelity: bool,
    strict_l10n: bool,
    strict_a11y: bool,
) -> bool:
    """Return True when a baked tier may proceed for the given text policy."""
    if policy in LIVE_BAKED_FORBIDDEN:
        return False
    if strict_l10n and localization_blocker(policy):
        return False
    if strict_a11y and policy == TextPolicyClass.LIVE_ACCESSIBILITY:
        return False
    return not (
        strict_fidelity
        and policy
        not in {
            TextPolicyClass.NONE,
            TextPolicyClass.DECORATIVE_STATIC,
            TextPolicyClass.MARKETING_STATIC,
        }
    )
