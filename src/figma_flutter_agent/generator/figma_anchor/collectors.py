"""Clean-tree candidate selection for layout anchor injection."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.figma_anchor.blocks import _extract_positioned_block
from figma_flutter_agent.generator.figma_anchor.coverage import _layout_node_covered_in_sources
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_CONTENT_BODY_WIDGET_RE = re.compile(
    r"\b(?:const\s+)?\w*(?:MainContent|ScreenBody|FormBody)\w*\s*\(",
)


def _collect_button_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.BUTTON and node.stack_placement is not None:
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _subtree_has_vector(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.VECTOR and node.vector_asset_key:
        return True
    return any(_subtree_has_vector(child) for child in node.children)


def _collect_chrome_stack_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        placement = node.stack_placement
        if (
            node.type == NodeType.STACK
            and placement is not None
            and placement.width is not None
            and placement.height is not None
            and placement.width <= 72
            and placement.height <= 72
            and placement.top < 120
            and _subtree_has_vector(node)
        ):
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _collect_text_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if (
            node.type == NodeType.TEXT
            and node.stack_placement is not None
            and (node.text or "").strip()
        ):
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _collect_decorative_vector_node_ids(root: CleanDesignTreeNode) -> list[str]:
    """Absolute vector overlays eligible for layout inject when widgets own chrome."""
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.VECTOR and node.stack_placement is not None:
            ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


_MIN_ABSENT_LAYOUT_INJECT_AREA = 5000.0


def _placement_area(node: CleanDesignTreeNode) -> float:
    placement = node.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return 0.0
    return float(placement.width) * float(placement.height)


def _collect_absent_root_positioned_subtrees(
    root: CleanDesignTreeNode,
    *,
    layout_code: str,
    screen_code: str,
    companion_sources: tuple[str, ...],
) -> list[str]:
    """Screen-root ``Positioned`` subtrees present in layout Dart but missing from the screen."""
    coverage = (screen_code, *companion_sources)
    missing: list[tuple[float, str]] = []
    for child in root.children:
        if child.stack_placement is None:
            continue
        if _placement_area(child) < _MIN_ABSENT_LAYOUT_INJECT_AREA:
            continue
        if child.type == NodeType.TEXT:
            continue
        if _layout_node_covered_in_sources(child.id, child, *coverage):
            continue
        if _extract_positioned_block(layout_code, child.id) is None:
            continue
        top = child.stack_placement.top
        missing.append((top, child.id))
    missing.sort(key=lambda item: item[0])
    return [node_id for _, node_id in missing]


def _collect_layout_injectable_node_ids(
    root: CleanDesignTreeNode,
    *,
    decorative_only: bool = False,
    layout_code: str = "",
    screen_code: str = "",
    companion_sources: tuple[str, ...] = (),
) -> list[str]:
    """Node ids eligible for layout Positioned injection."""
    seen: set[str] = set()
    ordered: list[str] = []
    if decorative_only:
        candidates = (
            *_collect_chrome_stack_node_ids(root),
            *_collect_decorative_vector_node_ids(root),
        )
    else:
        candidates = (
            *_collect_absent_root_positioned_subtrees(
                root,
                layout_code=layout_code,
                screen_code=screen_code,
                companion_sources=companion_sources,
            ),
            *_collect_button_node_ids(root),
            *_collect_text_node_ids(root),
            *_collect_chrome_stack_node_ids(root),
        )
    for node_id in candidates:
        if node_id in seen:
            continue
        seen.add(node_id)
        ordered.append(node_id)
    return ordered


_LAYOUT_CHROME_MARKERS = ("BoxShape.circle", "border: Border.all")

_LAYOUT_COMPLEXITY_TOKENS = (
    "Container(",
    "Stack(",
    "SvgPicture",
    "BoxDecoration",
    "Material(",
    "InkWell(",
    "border:",
)


def _collect_layout_upgrade_node_ids(root: CleanDesignTreeNode) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for node_id in (
        *_collect_button_node_ids(root),
        *_collect_chrome_stack_node_ids(root),
    ):
        if node_id in seen:
            continue
        seen.add(node_id)
        ordered.append(node_id)
    return ordered


def _layout_inject_suppressed_for_content_widget(
    screen_code: str,
    companion_sources: tuple[str, ...],
) -> bool:
    """Skip layout inject when the screen delegates UI to an extracted content widget."""
    del companion_sources
    return _CONTENT_BODY_WIDGET_RE.search(screen_code) is not None
