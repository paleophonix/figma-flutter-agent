"""Heuristics for interactive groups (classic absolute Figma layouts)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_INPUT_HINTS = ("email", "password", "phone", "username", "search", "name")
_ACTION_HINTS = (
    "continue with",
    "log in",
    "login",
    "sign up",
    "sign in",
    "submit",
    "get started",
    "register",
    "forgot password",
)
_MAX_CONTROL_HEIGHT = 120.0
_MAX_CONTROL_CHILDREN = 8
_MAX_LOCAL_DEPTH = 2


def _local_nodes(node: CleanDesignTreeNode, max_depth: int) -> list[CleanDesignTreeNode]:
    """Collect descendants up to ``max_depth`` without crossing other stack groups."""
    nodes: list[CleanDesignTreeNode] = []

    def walk(current: CleanDesignTreeNode, depth: int) -> None:
        if depth > max_depth:
            return
        nodes.append(current)
        if depth == max_depth:
            return
        for child in current.children:
            walk(child, depth + 1)

    for child in node.children:
        walk(child, 1)
    return nodes


def _is_structural_button_shell(child: CleanDesignTreeNode) -> bool:
    """Return True for inner layout stacks that only wrap one social-style button row."""
    if child.type != NodeType.STACK:
        return False
    local_nodes = _local_nodes(child, _MAX_LOCAL_DEPTH)
    has_surface = any(
        item.type == NodeType.CONTAINER
        and (item.style.background_color or item.style.border_color)
        for item in local_nodes
    )
    has_action_text = any(
        item.type == NodeType.TEXT
        and item.text
        and any(hint in item.text.lower() for hint in _ACTION_HINTS)
        for item in local_nodes
    )
    return has_surface and has_action_text


def stack_interaction_kind(node: CleanDesignTreeNode) -> str | None:
    """Classify absolute ``STACK`` groups as tap targets or text fields.

    Args:
        node: Parsed clean-tree node (typically ``STACK`` from a Figma ``GROUP``).

    Returns:
        ``"input"``, ``"button"``, or ``None``.
    """
    if node.type != NodeType.STACK:
        return None

    height = node.sizing.height
    if height is not None and height > _MAX_CONTROL_HEIGHT:
        return None
    if len(node.children) > _MAX_CONTROL_CHILDREN:
        return None

    nested_kind = next(
        (
            kind
            for child in node.children
            if child.type == NodeType.STACK
            and not _is_structural_button_shell(child)
            and (kind := stack_interaction_kind(child)) is not None
        ),
        None,
    )
    if nested_kind is not None:
        return None

    local_nodes = _local_nodes(node, _MAX_LOCAL_DEPTH)
    text_nodes = [n for n in local_nodes if n.type == NodeType.TEXT and n.text]
    if not text_nodes:
        return None
    surfaces = [
        n
        for n in local_nodes
        if n.type == NodeType.CONTAINER
        and (
            n.style.background_color is not None
            or n.style.border_color is not None
            or n.style.border_radius is not None
        )
    ]
    if not surfaces:
        return None

    for text_node in text_nodes:
        label = (text_node.text or text_node.name or "").strip().lower()
        if any(hint in label for hint in _INPUT_HINTS) and len(label) < 48:
            return "input"

    for text_node in text_nodes:
        label = (text_node.text or "").strip().lower()
        if any(hint in label for hint in _ACTION_HINTS):
            return "button"
    return None


def input_hint_text(node: CleanDesignTreeNode) -> str:
    """Return placeholder label for an input-like stack group."""
    hint_node = input_hint_node(node)
    if hint_node is not None and hint_node.text:
        return hint_node.text.strip()
    return node.accessibility_label or node.name


def input_hint_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the placeholder ``TEXT`` node inside an input-like stack group."""
    for text_node in _local_nodes(node, _MAX_LOCAL_DEPTH):
        if text_node.type == NodeType.TEXT and text_node.text:
            return text_node
    return None


def primary_surface_node(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Pick the main RECTANGLE surface inside a group (largest area)."""
    surfaces = [
        n
        for n in _local_nodes(node, _MAX_LOCAL_DEPTH)
        if n.type == NodeType.CONTAINER
        and n.sizing.width
        and n.sizing.height
        and (n.style.background_color or n.style.border_color)
    ]
    if not surfaces:
        return None
    return max(surfaces, key=lambda n: float(n.sizing.width or 0) * float(n.sizing.height or 0))


_LINK_HINTS = (
    "forgot password",
    "sign up",
    "sign in",
    "log in",
    "register",
    "terms",
    "privacy",
    "learn more",
    "reset password",
)


def is_link_text(text: str | None) -> bool:
    """Return True when ``text`` looks like a tappable inline link label."""
    if not text:
        return False
    label = text.strip().lower()
    if len(label) > 64:
        return False
    return any(hint in label for hint in _LINK_HINTS)
