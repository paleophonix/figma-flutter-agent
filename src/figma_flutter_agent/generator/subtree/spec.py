"""Subtree detection, candidate scoring, and spec building."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger  # noqa: F401  (used by callers via star-import path)

from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case
from figma_flutter_agent.parser.interaction import (
    looks_like_media_controls_stack,
    looks_like_password_field_stack,
    must_inline_extracted_widget_host,
    stack_interaction_kind,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MIN_VECTOR_NODES = 8
_MIN_SUBTREE_AREA = 12_000.0
_MIN_COMPACT_ICON_VECTORS = 2
_MAX_COMPACT_ICON_VECTORS = 12
_MAX_COMPACT_ICON_WIDTH = 64.0
_MAX_COMPACT_ICON_HEIGHT = 64.0
_GEOMETRY_SOCIAL_ROW_CONFIDENCE = 0.7
_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.TEXT,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
    }
)


@dataclass(frozen=True)
class SubtreeWidgetSpec:
    """Metadata for a deterministic subtree-backed widget."""

    node_id: str
    class_name: str
    file_name: str
    representative: CleanDesignTreeNode
    vector_count: int


@dataclass(frozen=True)
class SubtreeWidgetResult:
    """Generated subtree widget files."""

    files: dict[str, str]
    specs: tuple[SubtreeWidgetSpec, ...]


def _count_vector_nodes(node: CleanDesignTreeNode) -> int:
    total = 0
    if node.type in {NodeType.VECTOR, NodeType.IMAGE} or node.vector_asset_key or node.image_asset_key:
        total += 1
    for child in node.children:
        total += _count_vector_nodes(child)
    return total


def _count_interactive_nodes(node: CleanDesignTreeNode) -> int:
    total = 1 if node.type in _INTERACTIVE_TYPES else 0
    for child in node.children:
        total += _count_interactive_nodes(child)
    return total


def _subtree_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    return width * height


def _subtree_class_name(node: CleanDesignTreeNode, widget_suffix: str) -> str:
    base = to_pascal_case(node.name) or f"Subtree{node.id.replace(':', '')}"
    if base.endswith(widget_suffix):
        return base
    return f"{base}{widget_suffix}"


def _subtree_hosts_inline_form_field(node: CleanDesignTreeNode) -> bool:
    """True when any descendant must compile inline (INPUT / password stacks)."""
    if must_inline_extracted_widget_host(node):
        return True
    return any(_subtree_hosts_inline_form_field(child) for child in node.children)


def _is_subtree_candidate(node: CleanDesignTreeNode, *, is_direct_child: bool = False) -> bool:
    if _subtree_hosts_inline_form_field(node):
        return False
    if node.render_boundary:
        return False
    if node.vector_asset_key and not node.children:
        return False
    vector_count = _count_vector_nodes(node)
    min_vectors = 6 if is_direct_child else _MIN_VECTOR_NODES
    if vector_count < min_vectors:
        return False
    if not is_direct_child and _subtree_area(node) < _MIN_SUBTREE_AREA:
        return False
    interactive_count = _count_interactive_nodes(node)
    return vector_count > interactive_count


def _is_compact_icon_subtree(node: CleanDesignTreeNode) -> bool:
    """Detect small multicolor icon stacks (e.g. Google G) that LLMs often break."""
    if node.type != NodeType.STACK:
        return False
    vector_count = _count_vector_nodes(node)
    if vector_count < _MIN_COMPACT_ICON_VECTORS or vector_count > _MAX_COMPACT_ICON_VECTORS:
        return False
    placement = node.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return False
    if placement.width > _MAX_COMPACT_ICON_WIDTH or placement.height > _MAX_COMPACT_ICON_HEIGHT:
        return False
    return _count_interactive_nodes(node) < vector_count


def _with_screen_stack_placement(
    node: CleanDesignTreeNode,
    *,
    screen_left: float,
    screen_top: float,
) -> CleanDesignTreeNode:
    placement = node.stack_placement
    if placement is None:
        return node
    return node.model_copy(
        update={
            "stack_placement": placement.model_copy(
                update={"left": screen_left, "top": screen_top},
            ),
        },
    )


def _append_subtree_spec_from_ref(
    specs: list[SubtreeWidgetSpec],
    *,
    node: CleanDesignTreeNode,
    class_name: str,
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
) -> None:
    """Register a subtree widget already replaced by ``extracted_widget_ref`` on the tree."""
    if node.id in used_node_ids:
        return
    resolved_class = class_name
    file_name = to_snake_case(resolved_class)
    suffix = 2
    while file_name in used_file_names or resolved_class in used_class_names:
        resolved_class = f"{class_name}{suffix}"
        file_name = to_snake_case(resolved_class)
        suffix += 1
    used_file_names.add(file_name)
    used_class_names.add(resolved_class)
    used_node_ids.add(node.id)
    specs.append(
        SubtreeWidgetSpec(
            node_id=node.id,
            class_name=resolved_class,
            file_name=file_name,
            representative=node,
            vector_count=_count_vector_nodes(node),
        )
    )


def _append_subtree_spec(
    specs: list[SubtreeWidgetSpec],
    *,
    node: CleanDesignTreeNode,
    widget_suffix: str,
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
    screen_left: float | None = None,
    screen_top: float | None = None,
) -> None:
    if node.id in used_node_ids:
        return
    representative = node
    if screen_left is not None and screen_top is not None:
        representative = _with_screen_stack_placement(
            node,
            screen_left=screen_left,
            screen_top=screen_top,
        )
    base_class_name = _subtree_class_name(node, widget_suffix)
    class_name = base_class_name
    file_name = to_snake_case(class_name)
    suffix = 2
    while file_name in used_file_names or class_name in used_class_names:
        class_name = f"{base_class_name}{suffix}"
        file_name = to_snake_case(class_name)
        suffix += 1
    used_file_names.add(file_name)
    used_class_names.add(class_name)
    used_node_ids.add(node.id)
    specs.append(
        SubtreeWidgetSpec(
            node_id=node.id,
            class_name=class_name,
            file_name=file_name,
            representative=representative,
            vector_count=_count_vector_nodes(node),
        )
    )


def _social_button_subtree_ids(root: CleanDesignTreeNode) -> frozenset[str]:
    """Node ids inside auth buttons and geometry-detected social rows (icons stay in-button)."""
    from figma_flutter_agent.generator.subtree.auth_buttons import (
        _collect_social_auth_button_stacks,
    )
    from figma_flutter_agent.generator.subtree.merge import _collect_all_nodes
    from figma_flutter_agent.parser.geometry import auth_button_confidence

    ids: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        ids.add(node.id)
        for child in node.children:
            walk(child)

    for node in _collect_all_nodes(root):
        if node.type == NodeType.BUTTON and auth_button_confidence(node) >= _GEOMETRY_SOCIAL_ROW_CONFIDENCE:
            walk(node)
    for stack in _collect_social_auth_button_stacks(root):
        walk(stack)
    return frozenset(ids)


def _walk_compact_icon_subtrees(
    node: CleanDesignTreeNode,
    *,
    offset_left: float,
    offset_top: float,
    widget_suffix: str,
    specs: list[SubtreeWidgetSpec],
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
    excluded_node_ids: frozenset[str],
) -> None:
    from figma_flutter_agent.assets.composite_icons import is_composite_icon_export_node

    if is_composite_icon_export_node(node):
        return
    if node.id in excluded_node_ids:
        return
    ref = (node.extracted_widget_ref or "").strip()
    if ref:
        _append_subtree_spec_from_ref(
            specs,
            node=node,
            class_name=ref,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
        )
        return
    placement = node.stack_placement
    screen_left = offset_left + (placement.left if placement is not None else 0.0)
    screen_top = offset_top + (placement.top if placement is not None else 0.0)
    if _is_compact_icon_subtree(node):
        _append_subtree_spec(
            specs,
            node=node,
            widget_suffix=widget_suffix,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            screen_left=screen_left,
            screen_top=screen_top,
        )
    for child in node.children:
        _walk_compact_icon_subtrees(
            child,
            offset_left=screen_left,
            offset_top=screen_top,
            widget_suffix=widget_suffix,
            specs=specs,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            excluded_node_ids=excluded_node_ids,
        )


def collect_subtree_widget_specs(
    root: CleanDesignTreeNode,
    *,
    widget_suffix: str,
    reserved_file_names: set[str] | None = None,
) -> list[SubtreeWidgetSpec]:
    """Collect vector-rich direct child subtrees that should not be simplified by the LLM."""
    reserved = reserved_file_names or set()
    specs: list[SubtreeWidgetSpec] = []
    used_file_names = set(reserved)
    used_class_names: set[str] = set()
    used_node_ids: set[str] = set()

    social_ids = _social_button_subtree_ids(root)
    for child in root.children:
        ref = (child.extracted_widget_ref or "").strip()
        if ref:
            _append_subtree_spec_from_ref(
                specs,
                node=child,
                class_name=ref,
                used_file_names=used_file_names,
                used_class_names=used_class_names,
                used_node_ids=used_node_ids,
            )
            continue
        if child.id in social_ids:
            continue
        if (
            child.type == NodeType.INPUT
            or must_inline_extracted_widget_host(child)
            or stack_interaction_kind(child) == "input"
            or looks_like_password_field_stack(child)
            or looks_like_media_controls_stack(child)
        ):
            continue
        if not _is_subtree_candidate(child, is_direct_child=True):
            continue
        _append_subtree_spec(
            specs,
            node=child,
            widget_suffix=widget_suffix,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
        )

    excluded = social_ids | frozenset(used_node_ids)
    for child in root.children:
        if child.id in excluded:
            continue
        _walk_compact_icon_subtrees(
            child,
            offset_left=0.0,
            offset_top=0.0,
            widget_suffix=widget_suffix,
            specs=specs,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            excluded_node_ids=excluded,
        )
    return [spec for spec in specs if spec.node_id not in social_ids]


def build_subtree_widget_hints(specs: list[SubtreeWidgetSpec]) -> list[str]:
    """Build LLM hints for pre-rendered subtree widgets."""
    hints: list[str] = []
    for spec in specs:
        placement = spec.representative.stack_placement
        placement_hint = ""
        if (
            placement is not None
            and placement.width is not None
            and placement.height is not None
        ):
            placement_hint = (
                f" Place exactly one Positioned(left: {placement.left}, top: {placement.top}, "
                f"width: {placement.width}, height: {placement.height}, "
                f"child: const {spec.class_name}()) in screenCode."
            )
        hints.append(
            f"Prebuilt vector-rich subtree widget '{spec.class_name}' "
            f"(node {spec.node_id}, {spec.vector_count} vectors) is already generated at "
            f"lib/widgets/{spec.file_name}.dart.{placement_hint} "
            f"Use only `const {spec.class_name}()` for this subtree — do NOT inline SvgPicture "
            "stacks, abbreviate vector layers, redeclare the widget class in screenCode, or "
            "emit SizedBox.shrink() placeholder classes."
        )
    return hints
