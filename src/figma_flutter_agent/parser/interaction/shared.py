"""Shared low-level helpers used across interaction predicate submodules."""

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
    "save",
    "no thanks",
)
_SINGLE_WORD_ACTION_LABELS = frozenset(
    {
        "start",
        "play",
        "ok",
        "go",
        "home",
        "music",
        "meditate",
        "sleep",
        "all",
        "my",
        "save",
    }
)
WEEKDAY_CHIP_ROW_NAME = "WeekdayChipRow"
_WEEKDAY_CHIP_LABELS = frozenset({"su", "m", "t", "w", "th", "f", "s"})
_WEEKDAY_CHIP_MIN_SIZE = 32.0
_WEEKDAY_CHIP_MAX_SIZE = 56.0
_MAX_CONTROL_HEIGHT = 120.0
_MAX_CONTROL_CHILDREN = 8
_MAX_LOCAL_DEPTH = 2
_BACK_NAV_DESCENDANT_DEPTH = 6
_INPUT_TRAILING_ICON_DESCENDANT_DEPTH = 6
_COMPACT_ICON_ACTION_MIN = 20.0
_COMPACT_ICON_ACTION_MAX = 43.0
_ICON_ACTION_NAME_HINTS = (
    "arrow",
    "back",
    "close",
    "chevron",
    "caret",
    "nav",
    "narrow",
)
_STROKE_AXIS_MIN_SPAN = 8.0
_STROKE_AXIS_MAX_THICKNESS = 2.5


def _label_matches_action_hint(label: str) -> bool:
    normalized = label.strip().lower()
    if not normalized:
        return False
    if normalized in _SINGLE_WORD_ACTION_LABELS:
        return True
    return any(hint in normalized for hint in _ACTION_HINTS)


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


def _argb_color_key(value: str | None) -> str:
    """Normalize ARGB hex strings for stable equality checks."""
    if not value:
        return ""
    stripped = value.strip()
    if stripped.startswith(("0x", "0X")) and len(stripped) >= 10:
        return f"0x{stripped[2:].upper()}"
    if stripped.startswith("#") and len(stripped) == 9:
        return f"0x{stripped[1:].upper()}"
    return stripped.upper()


def _descendant_nodes(node: CleanDesignTreeNode, max_depth: int) -> list[CleanDesignTreeNode]:
    """Collect descendants up to ``max_depth`` levels below ``node`` (inclusive of ``node``)."""
    nodes: list[CleanDesignTreeNode] = [node]

    def walk(current: CleanDesignTreeNode, depth: int) -> None:
        if depth >= max_depth:
            return
        for child in current.children:
            nodes.append(child)
            walk(child, depth + 1)

    walk(node, 0)
    return nodes


def _subtree_text_node_count(node: CleanDesignTreeNode, depth: int = 0) -> int:
    _LIST_TILE_TEXT_SEARCH_DEPTH = 8
    if depth > _LIST_TILE_TEXT_SEARCH_DEPTH:
        return 0
    count = 1 if node.type == NodeType.TEXT and node.text else 0
    for child in node.children:
        count += _subtree_text_node_count(child, depth + 1)
    return count
